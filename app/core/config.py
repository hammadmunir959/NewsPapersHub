import os

# ── Base Paths ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEWSPAPERS_DIR = os.path.join(PROJECT_ROOT, "newspapers")

# ── Supported Newspapers ────────────────────────────────────
SUPPORTED_NEWSPAPERS = ["dawn", "thenews"]

# ── DAWN Configuration ──────────────────────────────────────
DAWN_SECTIONS = [
    "front-page", "national", "international", "editorial", "opinion",
    "letters", "business", "metro-islamabad", "sport", "back-page"
]
DAWN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
DAWN_ARTICLE_CONCURRENCY = 4
DAWN_SECTION_CONCURRENCY = 3
DAWN_MAX_ARTICLES_PER_SECTION = 25
DAWN_REQUEST_DELAY = 0.5

# ── THE NEWS Configuration ──────────────────────────────────
THENEWS_CITIES = ["islamabad", "karachi", "lahore", "peshawar", "rawalpindi"]
THENEWS_PDF_BASE = "https://e.thenews.com.pk/static_pages"

# ── PDF Generation Config ───────────────────────────────────
PDF_MARGIN = 25
PDF_COL_GAP = 10
PDF_FRONT_MASTHEAD_HEIGHT = 220
PDF_SECTION_MASTHEAD_HEIGHT = 100
PDF_MASTHEAD_COL_GAP = 12
PDF_RUNNING_HEADER_HEIGHT = 28

PDF_CONFIG = {
    "global": {
        "col_count": 4,
        "font_body": "Times-Roman",
        "font_headline": "Times-Bold",
    },
    "dawn": {
        "masthead_height": 160, # Dynamic base
        "logo_text": "DAWN",
        "portrait_path": os.path.join(PROJECT_ROOT, "app/core/assets/quaid.jpg"),
    }
}


