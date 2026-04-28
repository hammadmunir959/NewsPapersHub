import os
import asyncio
import logging
from typing import List, Optional
import aiohttp
from bs4 import BeautifulSoup  # now used for robust image URL extraction
from PIL import Image
import io

from app.core.config import THENEWS_CITIES, THENEWS_PDF_BASE
from app.utils.path_utils import get_newspaper_dir, get_pdf_path
from app.models.schemas import PaperSuccessResponse, TaskState
from app.services.task_manager_service import task_manager

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Configuration – easily shared and overridden
# ────────────────────────────────────────────────────────────
THENEWS_CONFIG = {
    "base_url": "https://e.thenews.pk",
    "city_slug": {
        "islamabad": "pindi",
        "karachi":   "karachi",
        "lahore":    "lahore",
        "peshawar":  "peshawar",
    },
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://e.thenews.pk/",
    },
    "timeout": aiohttp.ClientTimeout(total=30),
    "page_limit": 50,  # max pages to probe
}

# ────────────────────────────────────────────────────────────
# Helper: merge a list of JPEG/PNG bytes into a PDF
# ────────────────────────────────────────────────────────────
def merge_images_to_pdf(image_bytes_list: List[bytes], output_path: str):
    """Merge multiple image pages into a single PDF using Pillow."""
    pil_images = [Image.open(io.BytesIO(b)).convert("RGB") for b in image_bytes_list]
    pil_images[0].save(
        output_path, save_all=True, append_images=pil_images[1:], format="PDF"
    )
    logger.info("PDF saved: %s (%d pages)", output_path, len(pil_images))

# ────────────────────────────────────────────────────────────
# Lightweight fetcher for the e‑paper viewer HTML + image download
# ────────────────────────────────────────────────────────────
class TheNewsEpubFetcher:
    """
    Fetches the epaper page viewer HTML and extracts the high‑resolution image URL.
    Uses aiohttp for fully asynchronous I/O.
    """
    def __init__(self, config: dict = None):
        cfg = config or THENEWS_CONFIG
        self.base_url = cfg["base_url"]
        self.headers = cfg["headers"]
        self.timeout = cfg["timeout"]
        self.city_slug = cfg["city_slug"]

    def _build_page_url(self, city: str, date_slug: str, page: int) -> str:
        slug = self.city_slug.get(city, city)
        return f"{self.base_url}/{slug}/{date_slug}/page{page}"

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetch the page viewer HTML. Returns None on non‑200 or error."""
        try:
            async with session.get(url, headers=self.headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as exc:
            logger.debug("Failed to fetch %s: %s", url, exc)
        return None

    async def get_image_url(self, session: aiohttp.ClientSession, city: str,
                            date_slug: str, page: int) -> Optional[str]:
        """
        Given city/date/page, fetch the page viewer and extract the image URL.
        """
        url = self._build_page_url(city, date_slug, page)
        html = await self._fetch_html(session, url)
        if not html:
            return None

        # Offload BeautifulSoup parsing to a thread executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_image_url, html)

    def _parse_image_url(self, html: str) -> Optional[str]:
        """CPU-bound BeautifulSoup parsing (runs in executor)."""
        soup = BeautifulSoup(html, "html.parser")
        # Look for the main page image (id='mainImg' is the most common pattern)
        img = soup.select_one("img#mainImg") or soup.select_one("img[src*='static_pages']")
        if not img or not img.get("src"):
            return None

        src = img["src"]
        if src.startswith("http"):
            return src
        return f"{self.base_url}{src}" if src.startswith("/") else f"{self.base_url}/{src}"

    async def download_image(self, session: aiohttp.ClientSession, image_url: str) -> Optional[bytes]:
        """Download the image bytes."""
        try:
            async with session.get(image_url, headers=self.headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception as exc:
            logger.error("Image download failed: %s – %s", image_url, exc)
        return None

# ────────────────────────────────────────────────────────────
# The main service (orchestration layer)
# ────────────────────────────────────────────────────────────
class TheNewsService:
    """
    Service for The News International e‑paper.
    Downloads city editions as images and merges them into PDFs.
    """

    @staticmethod
    def _build_date_slug(date_str: str) -> str:
        """2026-04-14 → 14-04-2026"""
        parts = date_str.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"

    @staticmethod
    async def _download_city(date_str: str, city: str, task_id: Optional[str] = None) -> Optional[str]:
        """
        Download all pages for one city, merge into a PDF.
        Returns the PDF path or None on failure.
        """
        dest = get_pdf_path("thenews", date_str, method=city)
        if os.path.exists(dest):
            logger.info("[thenews/%s] Already cached: %s", city, dest)
            return dest

        date_slug = TheNewsService._build_date_slug(date_str)
        fetcher = TheNewsEpubFetcher(THENEWS_CONFIG)

        if task_id:
            await task_manager.publish(task_id, TaskState.DISCOVERING, 10,
                                       f"[{city}] Starting page discovery...")

        page_images: List[bytes] = []
        async with aiohttp.ClientSession() as session:
            for page in range(1, THENEWS_CONFIG["page_limit"] + 1):
                # discover image URL
                img_url = await fetcher.get_image_url(session, city, date_slug, page)
                if not img_url:
                    logger.info("[thenews/%s] No more pages after page %d", city, page-1)
                    break

                # download image bytes
                logger.info("[thenews/%s] Downloading page %d: %s", city, page, img_url)
                pct = min(80, 10 + (page * 2))
                if task_id:
                    await task_manager.publish(task_id, TaskState.DOWNLOADING, pct,
                                               f"[{city}] Downloading page {page}...")

                img_bytes = await fetcher.download_image(session, img_url)
                if img_bytes is None:
                    logger.error("[thenews/%s] Failed to download page %d image", city, page)
                    break

                page_images.append(img_bytes)
                logger.info("[thenews/%s] ✓ Page %d (%d KB)", city, page, len(img_bytes)//1024)

        if not page_images:
            logger.error("[thenews/%s] No pages downloaded for %s", city, date_str)
            if task_id:
                await task_manager.publish(task_id, TaskState.ERROR, 50,
                                           f"[{city}] No pages found")
            return None

        # Merge images into PDF
        if task_id:
            await task_manager.publish(task_id, TaskState.BUILDING_PDF, 85,
                                       f"[{city}] Merging {len(page_images)} pages...")

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, merge_images_to_pdf, page_images, dest)
        except Exception as e:
            logger.exception("[thenews/%s] PDF merge failed", city)
            if task_id:
                await task_manager.publish(task_id, TaskState.ERROR, 85,
                                           f"[{city}] PDF merge failed: {e}")
            return None

        logger.info("[thenews/%s] ✓ PDF saved to %s", city, dest)
        return dest

    @staticmethod
    async def process(date_str: str, cities: Optional[List[str]] = None,
                      task_id: Optional[str] = None) -> List[PaperSuccessResponse]:
        """Main entry point – returns a list of responses for each city."""
        target_cities = cities or THENEWS_CITIES
        os.makedirs(get_newspaper_dir("thenews"), exist_ok=True)

        msg = f"[thenews] Downloading for {date_str}, cities={target_cities}"
        logger.info(msg)
        if task_id:
            await task_manager.publish(task_id, TaskState.DISCOVERING, 5, msg)

        tasks = [
            TheNewsService._download_city(date_str, city, task_id)
            for city in target_cities
        ]
        results = await asyncio.gather(*tasks)

        responses = []
        for city, path in zip(target_cities, results):
            if path:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                responses.append(PaperSuccessResponse(
                    newspaper="thenews",
                    date=date_str,
                    file_name=os.path.basename(path),
                    path=path,
                    pages=0,
                    size_mb=round(size_mb, 2),
                ))
        return responses