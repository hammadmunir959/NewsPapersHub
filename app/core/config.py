import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ── Base Paths ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEWSPAPERS_DIR = os.path.join(PROJECT_ROOT, "newspapers")

# ── Supported Newspapers ────────────────────────────────────
SUPPORTED_NEWSPAPERS = ["dawn", "thenews"]

# ── DAWN Configuration ──────────────────────────────────────
DAWN_RSS_FEEDS = {
    "home": "https://www.dawn.com/feeds/home",
    "latest-news": "https://www.dawn.com/feeds/latest-news",
    "pakistan": "https://www.dawn.com/feeds/pakistan",
    "world": "https://www.dawn.com/feeds/world",
    "business": "https://www.dawn.com/feeds/business",
    "sport": "https://www.dawn.com/feeds/sport",
    "opinion": "https://www.dawn.com/feeds/opinion",
    "tech": "https://www.dawn.com/feeds/tech",
    "magazines": "https://www.dawn.com/feeds/magazines",
    "prism": "https://www.dawn.com/feeds/prism"
}
DAWN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
DAWN_ARTICLE_CONCURRENCY = 4
DAWN_REQUEST_DELAY = 0.5

# ── THE NEWS Configuration ──────────────────────────────────
THENEWS_CITIES = ["islamabad", "karachi", "lahore"]
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
        "display_name": "DAWN",
        "logo_text": "DAWN",
        "tagline": "F O U N D E D   B Y   Q U A I D - I - A Z A M   M O H A M M A D   A L I   J I N N A H",
        "location": "KARACHI",
        "portrait_path": os.path.join(PROJECT_ROOT, "app/core/assets/quaid.jpg"),
        "masthead_font": "Times-Bold",
        "masthead_font_size": 80,
    },
    "thenews": {
        "display_name": "THE NEWS",
        "logo_text": "THE NEWS",
        "tagline": "INTERNATIONAL",
        "location": "ISLAMABAD",
        "portrait_path": None,
        "masthead_font": "Times-Bold",
        "masthead_font_size": 70,
    }
}


# ── Security Configuration ──────────────────────────────────
APP_API_KEY = os.getenv("APP_API_KEY", "")
