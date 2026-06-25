"""Tesseract OCR for image captures (``deu+eng``).

Tesseract is a local, free OCR engine. The binary and the German language pack
are configured in :mod:`core.config` (the German pack lives in a user-writable
``tessdata`` dir because Program Files needs admin rights to write into).

``pytesseract`` is imported lazily inside the function so the rest of the
pipeline still imports if OCR isn't set up on a given machine.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.config import (
    TESSERACT_EXE,
    TESSERACT_LANG,
    TESSERACT_TESSDATA_DIR,
    get_logger,
)

logger = get_logger(__name__)


class OCRUnavailable(RuntimeError):
    """Raised when Tesseract or pytesseract is not installed/configured."""


def ocr_image(image_path: Path) -> str:
    """Return OCR text for an image using Tesseract ``deu+eng``.

    Raises :class:`OCRUnavailable` if pytesseract/the binary is missing so the
    watcher can log-and-skip (leaving the capture to retry) rather than crash.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise OCRUnavailable(
            "pytesseract/Pillow not installed. Run: pip install -r requirements.txt"
        ) from exc

    if not TESSERACT_EXE.exists():
        raise OCRUnavailable(
            f"Tesseract binary not found at {TESSERACT_EXE}. Install it "
            "(winget install UB-Mannheim.TesseractOCR) or set TESSERACT_EXE."
        )
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)

    # Point Tesseract at the tessdata dir that actually has the deu pack. Set it
    # via TESSDATA_PREFIX (env) rather than the --tessdata-dir config string:
    # pytesseract splits config on spaces and keeps quotes literally, which
    # mangles any path. Tesseract 5 accepts the tessdata dir directly here.
    if TESSERACT_TESSDATA_DIR.exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSERACT_TESSDATA_DIR)

    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img, lang=TESSERACT_LANG)
    text = text.strip()
    logger.info("OCR %s -> %d chars", image_path.name, len(text))
    return text
