import os

# ── Base Paths ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEWSPAPERS_DIR = os.path.join(PROJECT_ROOT, "newspapers")

# ── Supported Newspapers ────────────────────────────────────
SUPPORTED_NEWSPAPERS = ["dawn"]
SUPPORTED_METHODS = ["epaper", "text"]

# ── Dawn-specific Config ────────────────────────────────────
DAWN_CDN_BASE = "https://e.dawn.com"
DAWN_MAX_PAGES = 30
DAWN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ── PDF Generation Config ───────────────────────────────────
PDF_MARGIN = 40
PDF_COL_GAP = 18
PDF_HEADER_HEIGHT = 45           # Persistent top-bar
PDF_SECTION_MASTHEAD_HEIGHT = 120 # Large section banner

PDF_CONFIG = {
    "global": {
        "col_count": 4,
        "font_body": "Times-Roman",
        "font_headline": "Times-Bold",
    },
    "dawn": {
        "masthead_height": 160, # Dynamic base
        "logo_text": "DAWN",
        "portrait_path": "core/assets/quaid.jpg",
    }
}


# ── Helpers ─────────────────────────────────────────────────
def get_newspaper_dir(newspaper: str) -> str:
    """Return the storage directory for a newspaper, e.g. newspapers/dawn/"""
    return os.path.join(NEWSPAPERS_DIR, newspaper.lower())


def get_pdf_filename(newspaper: str, date_str: str, method: str = "") -> str:
    """Return PDF filename, e.g. dawn_12_04_2026_epaper.pdf"""
    year, month, day = date_str.split("-")
    suffix = f"_{method}" if method else ""
    return f"{newspaper.lower()}_{day}_{month}_{year}{suffix}.pdf"


def get_pdf_path(newspaper: str, date_str: str, method: str = "") -> str:
    """Return full path to the PDF file."""
    return os.path.join(get_newspaper_dir(newspaper), get_pdf_filename(newspaper, date_str, method))
