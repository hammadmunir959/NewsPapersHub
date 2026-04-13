import os
from app.core.config import NEWSPAPERS_DIR

def get_newspaper_dir(newspaper: str) -> str:
    """Return the storage directory for a newspaper, e.g. newspapers/dawn/"""
    return os.path.join(NEWSPAPERS_DIR, newspaper.lower())

def get_pdf_filename(newspaper: str, date_str: str, method: str = "") -> str:
    """Return PDF filename, e.g. dawn_12_04_2026.pdf"""
    year, month, day = date_str.split("-")
    suffix = f"_{method}" if method else ""
    return f"{newspaper.lower()}_{day}_{month}_{year}{suffix}.pdf"

def get_pdf_path(newspaper: str, date_str: str, method: str = "") -> str:
    """Return full path to the PDF file."""
    return os.path.join(get_newspaper_dir(newspaper), get_pdf_filename(newspaper, date_str, method))
