from __future__ import annotations
import os
from typing import Dict, List, Tuple
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import io

SUPPORTED_LANGS = "fra+nld"

SECTION_KEYWORDS = {
    "entries": ["entrées", "entrees", "voorgerechten", "vooraf"],
    "plats": ["plats", "hoofdgerecht", "hoofdgerechten", "gerechten"],
    "desserts": ["desserts", "nagerechten", "dessert"],
    "formules": ["formule", "formules", "menu", "menus"],
}


def _extract_text_pymupdf(pdf_path: str) -> str:
    text_parts: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)


def _ocr_scanned_pdf(pdf_path: str) -> str:
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


def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())


def build_lexicon_from_text(text: str) -> Dict[str, List[str]]:
    # Initialize sections
    lexicon: Dict[str, List[str]] = {k: [] for k in SECTION_KEYWORDS.keys()}
    current_section = None
    for raw_line in text.splitlines():
        line = normalize(raw_line)
        if not line:
            continue
        # Detect section
        for sec, kws in SECTION_KEYWORDS.items():
            if any(kw in line for kw in kws):
                current_section = sec
                break
        else:
            # Regular line: consider as dish if not a price-only line
            if current_section:
                # Remove trailing prices like 12,00 € or € 12.50
                cleaned = line
                # simple price patterns
                for sym in ["€", "eur", "euro", ",", ".", "-"]:
                    cleaned = cleaned.replace(" €", " ")
                # drop very short lines
                if len(cleaned) > 2:
                    # stop at double spaces or tabs where description continues
                    item = cleaned.split("  ")[0].strip(" -•·:;|\t")
                    if item and item not in lexicon[current_section]:
                        lexicon[current_section].append(item)
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
