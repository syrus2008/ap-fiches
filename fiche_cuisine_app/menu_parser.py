from __future__ import annotations
import os
from typing import Dict, List, Tuple
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import io
import re
import logging

SUPPORTED_LANGS = "fra+nld"
logger = logging.getLogger(__name__)

SECTION_KEYWORDS = {
    "entries": [
        "entrée", "entrées", "entree", "entrees",
        "entrées froides", "entrées chaudes",
        "voorgerecht", "voorgerechten", "vooraf",
        "starters", "suggesties", "suggestions",
        "soep", "soepen", "salade", "salades"
    ],
    "plats": [
        "plat", "plats", "plats principaux", "salé", "sale", "salé ",
        "hoofdgerecht", "hoofdgerechten", "gerechten", "gerechten hoofd",
        "viandes", "poissons", "pâtes", "pates", "pasta",
        "pizzas", "burgers", "vleesgerechten", "visgerechten", "hartig"
    ],
    "desserts": [
        "dessert", "desserts", "desserts maison", "sucré", "sucre",
        "nagerecht", "nagerechten", "ijs", "glaces", "zoet"
    ],
    "formules": ["formule", "formules", "menu", "menus", "menu du jour", "dagmenu"],
}


def _extract_text_pymupdf(pdf_path: str) -> str:
    logger.info(f"MENU: extracting text via PyMuPDF from {pdf_path}")
    text_parts: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)


def _ocr_scanned_pdf(pdf_path: str) -> str:
    logger.info(f"MENU: OCR fallback via Tesseract for {pdf_path}")
    images = convert_from_path(pdf_path, dpi=200)
    buf = io.StringIO()
    for img in images:
        text = pytesseract.image_to_string(img, lang=SUPPORTED_LANGS, config="--oem 3 --psm 6")
        buf.write(text)
        buf.write("\n")
    return buf.getvalue()


def extract_menu_text(pdf_path: str) -> str:
    text = _extract_text_pymupdf(pdf_path)
    if not text or len(text.strip()) < 10:
        # likely scanned
        text = _ocr_scanned_pdf(pdf_path)
    return text


def extract_menu_text_force_ocr(pdf_path: str) -> str:
    """Always OCR the PDF pages (useful if PyMuPDF text misses visual text)."""
    return _ocr_scanned_pdf(pdf_path)


def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())


PRICE_RE = re.compile(r"(\b\d{1,3}(?:[\.,]\d{1,2})?\b)\s*(?:€|eur|euro)?", re.IGNORECASE)


def _is_section_heading(line: str) -> str | None:
    """Return section key if the line is a heading, else None.
    We consider headings that are short and mostly just the section word(s).
    """
    stripped = line.strip(" -•·:\t|")
    # very short headings (1-3 words) matching keywords
    for sec, kws in SECTION_KEYWORDS.items():
        for kw in kws:
            # exact or startswith match, not mid-sentence
            if stripped == kw or stripped.startswith(kw + ":"):
                return sec
    return None


def _clean_dish_line(line: str) -> str:
    # remove price tokens
    line = PRICE_RE.sub("", line)
    # remove leading bullets/dashes and extra spaces
    line = line.strip(" -•·:\t|")
    line = re.sub(r"\s{2,}", " ", line)
    return line


def build_lexicon_from_text(text: str, only_formules: bool = False, forced_section: str | None = None) -> Dict[str, List[str]]:
    """Build a lexicon from PDF text.

    - If only_formules=True: collect items only under 'formules' section.
    - Otherwise: collect under entries/plats/desserts and ignore lines mentioning 'menu/formule' when misaligned.
    """
    lexicon: Dict[str, List[str]] = {k: [] for k in SECTION_KEYWORDS.keys()}
    current_section: str | None = None
    lines = text.splitlines()
    # Debug preview of text
    preview = "\n".join(lines[:30])
    logger.debug(f"MENU: text preview (first 30 lines)\n{preview}")
    for raw_line in lines:
        low = normalize(raw_line)
        if not low:
            continue
        # Detect a heading if line is short
        sec = _is_section_heading(low)
        if sec:
            current_section = sec
            continue

        # Skip obvious non-dish lines
        if len(low) <= 2 or low.isdigit():
            continue

        # If it's a 'menu/formule' mention but we are not building formules, skip
        if not only_formules and any(kw in low for kw in SECTION_KEYWORDS["formules"]):
            # Do not flip current section to formules automatically; treat as non-dish
            continue

        # Choose section
        target_section: str | None = None
        if only_formules:
            target_section = "formules"
        else:
            # Use current_section only if it's entries/plats/desserts
            if current_section in ("entries", "plats", "desserts"):
                target_section = current_section
            else:
                # Try weak detection: if line contains any section keyword (non-formule)
                for sec_try in ("entries", "plats", "desserts"):
                    if any(kw in low for kw in SECTION_KEYWORDS[sec_try]):
                        current_section = sec_try
                        target_section = sec_try
                        break
                # If still nothing and a forced section is provided, use it
                if not target_section and forced_section in ("entries", "plats", "desserts"):
                    target_section = forced_section

        if not target_section:
            continue

        cleaned = _clean_dish_line(low)
        if len(cleaned) < 3:
            continue
        # Avoid generic words
        if cleaned in ("entrée", "entree", "plat", "dessert"):
            continue
        if cleaned not in lexicon[target_section]:
            lexicon[target_section].append(cleaned)
    # Log counts
    for sec_key, items in lexicon.items():
        logger.info(f"MENU: built {len(items)} item(s) for section '{sec_key}' (only_formules={only_formules})")
    return lexicon


def merge_lexicons(base: Dict[str, List[str]], new: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out = {k: list(base.get(k, [])) for k in SECTION_KEYWORDS.keys()}
    for sec, items in new.items():
        existing = set(out.get(sec, []))
        for it in items:
            if it not in existing:
                out.setdefault(sec, []).append(it)
                existing.add(it)
    return out
