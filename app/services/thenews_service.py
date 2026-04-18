import os
import asyncio
import logging
import urllib.request
import urllib.error
from app.core.config import THENEWS_CITIES, THENEWS_PDF_BASE
from app.utils.path_utils import get_newspaper_dir, get_pdf_path
from app.models.schemas import PaperSuccessResponse

logger = logging.getLogger(__name__)

# New base: e.thenews.pk  (not e.thenews.com.pk)
THENEWS_BASE = "https://e.thenews.pk"

# City slug mapping — URL uses 'pindi' not 'islamabad'
CITY_SLUG = {
    "islamabad": "pindi",
    "karachi":   "karachi",
    "lahore":    "lahore",
    "peshawar":  "peshawar",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://e.thenews.pk/",
}


class TheNewsService:
    """
    Service for The News International (e.thenews.pk).
    Scrapes per-page images from  /{city}/{DD-MM-YYYY}/page{N}
    and saves each page as a PNG, then merges into a PDF.
    """

    @staticmethod
    def _build_date_slug(date_str: str) -> str:
        """
        YYYY-MM-DD  →  DD-MM-YYYY
        e.g. 2026-04-14 → 14-04-2026
        """
        year, month, day = date_str.split("-")
        return f"{day}-{month}-{year}"

    @staticmethod
    def _build_page_url(city: str, date_slug: str, page: int) -> str:
        """
        https://e.thenews.pk/pindi/14-04-2026/page1
        """
        slug = CITY_SLUG.get(city, city)
        return f"{THENEWS_BASE}/{slug}/{date_slug}/page{page}"

    @staticmethod
    def _fetch_page_image_url(page_url: str) -> str | None:
        """
        Fetch the HTML of a page-viewer URL and extract the full-res
        image src (typically an <img id="mainImg"> or similar).
        Returns None if the page doesn't exist (404 / no image found).
        """
        import re
        req = urllib.request.Request(page_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status != 200:
                    return None
                html = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError:
            return None

        # The epaper viewer embeds the page scan as a full-res image.
        # Adjust this pattern if the HTML structure changes.
        match = re.search(
            r'<img[^>]+id=["\']mainImg["\'][^>]+src=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        ) or re.search(
            r'<img[^>]+src=["\']([^"\']*static_pages[^"\']+\.(?:jpg|png|webp))["\']',
            html, re.IGNORECASE
        )
        if not match:
            return None

        src = match.group(1)
        if src.startswith("http"):
            return src
        return THENEWS_BASE + ("" if src.startswith("/") else "/") + src

    @staticmethod
    def _download_bytes(url: str) -> bytes:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    @staticmethod
    async def _download_city(
        date_str: str, city: str
    ) -> str | None:
        date_slug = TheNewsService._build_date_slug(date_str)
        dest = get_pdf_path("thenews", date_str, method=city)

        if os.path.exists(dest):
            logger.info(f"[thenews/{city}] Already exists: {dest}")
            return dest

        loop = asyncio.get_running_loop()
        page_images: list[bytes] = []
        page = 1

        while True:
            page_url = TheNewsService._build_page_url(city, date_slug, page)
            logger.info(f"[thenews/{city}] Fetching page {page}: {page_url}")

            # Get the image URL embedded in the viewer HTML
            img_url = await loop.run_in_executor(
                None, TheNewsService._fetch_page_image_url, page_url
            )
            if img_url is None:
                logger.info(f"[thenews/{city}] No more pages after page {page - 1}")
                break

            try:
                img_bytes = await loop.run_in_executor(
                    None, TheNewsService._download_bytes, img_url
                )
                page_images.append(img_bytes)
                logger.info(
                    f"[thenews/{city}] ✓ Page {page} ({len(img_bytes)//1024} KB)"
                )
            except Exception as e:
                logger.error(f"[thenews/{city}] ✗ Failed to download page {page} image: {e}")
                break

            page += 1

        if not page_images:
            logger.error(f"[thenews/{city}] No pages downloaded for {date_str}")
            return None

        # Merge all page images into a single PDF
        try:
            from PIL import Image
            import io

            pil_images = [Image.open(io.BytesIO(b)).convert("RGB") for b in page_images]
            pil_images[0].save(
                dest, save_all=True, append_images=pil_images[1:], format="PDF"
            )
            logger.info(f"[thenews/{city}] ✓ Saved {len(pil_images)}-page PDF → {dest}")
            return dest
        except Exception as e:
            logger.error(f"[thenews/{city}] ✗ PDF merge failed: {e}")
            return None

    @staticmethod
    async def process(
        date_str: str, cities: list[str] | None = None
    ) -> list[PaperSuccessResponse]:
        target_cities = cities or THENEWS_CITIES
        target_dir = get_newspaper_dir("thenews")
        os.makedirs(target_dir, exist_ok=True)

        logger.info(f"[thenews] Downloading for {date_str}, cities={target_cities}")

        tasks = [
            TheNewsService._download_city(date_str, city)
            for city in target_cities
        ]
        results = await asyncio.gather(*tasks)

        responses = []
        for city, path in zip(target_cities, results):
            if path:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                responses.append(PaperSuccessResponse(
                    status="success",
                    message=f"Successfully downloaded PDF for {city}",
                    newspaper="thenews",
                    date=date_str,
                    file_name=os.path.basename(path),
                    saved_at=path,
                    pages=0,
                    size_mb=round(size_mb, 2),
                ))

        return responses