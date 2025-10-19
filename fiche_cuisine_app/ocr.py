import os
from typing import List, Tuple, Optional
import cv2
import numpy as np
import pytesseract
from PIL import Image
import io

# Configure Tesseract command from env if provided
TESSERACT_CMD = os.environ.get("TESSERACT_CMD")
if TESSERACT_CMD and os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

SUPPORTED_LANGS = "fra+nld"  # French + Dutch (Belgium)


def _auto_contrast(gray: np.ndarray) -> np.ndarray:
    # CLAHE improves OCR robustness on screenshots
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Load an image from bytes and return a preprocessed grayscale np.ndarray."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    np_img = np.array(image)
    gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
    gray = _auto_contrast(gray)
    # Light denoise
    gray = cv2.bilateralFilter(gray, 5, 75, 75)
    # Adaptive threshold for crisp text
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 10)
    return bw


def ocr_text(image: np.ndarray, lang: str = SUPPORTED_LANGS) -> str:
    # Use LSTM OCR with configuration tuned for UI text
    custom_oem_psm_config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(image, lang=lang, config=custom_oem_psm_config)
    return text


def find_reservation_notes(full_text: str) -> List[str]:
    """Extract lines after the 'Note sur la réservation' / NL equivalent blocks.

    We capture up to a blank line or next card separator.
    """
    lines = [l.strip() for l in full_text.splitlines()]
    notes: List[str] = []

    start_markers = [
        "note sur la réservation",  # fr
        "note sur la reservation",
        "notitie bij de reservering",  # nl
        "opmerking bij de reservering",  # nl alt
    ]

    i = 0
    while i < len(lines):
        line = lines[i].lower()
        if any(m in line for m in start_markers):
            # Collect subsequent non-empty lines until a separator-like line
            i += 1
            block: List[str] = []
            while i < len(lines) and lines[i].strip():
                # stop if next card header pattern like a time or name line is detected
                if any(tok in lines[i] for tok in ["Pax", "tables", "Créée", "Gemaakt", "PAX", "pax"]):
                    break
                block.append(lines[i])
                i += 1
            if block:
                notes.append(" ".join(block))
        else:
            i += 1
    return notes


# Convenience for Streamlit: process raw bytes and directly return detected notes

def notes_from_image_bytes(image_bytes: bytes) -> Tuple[str, List[str]]:
    processed = preprocess_image(image_bytes)
    text = ocr_text(processed)
    notes = find_reservation_notes(text)
    return text, notes
