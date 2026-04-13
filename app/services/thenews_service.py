import os
import asyncio
import logging
import urllib.request
import urllib.error
from app.core.config import THENEWS_CITIES, THENEWS_PDF_BASE
from app.utils.path_utils import get_newspaper_dir
from app.models.schemas import PaperSuccessResponse

logger = logging.getLogger(__name__)

class TheNewsService:
    """
    Service for The News International.
    Downloads the full daily PDF from the e-paper server.
    """

    @staticmethod
    def _build_pdf_url(date_str: str, city: str) -> str:
        """
        Convert YYYY-MM-DD -> M-D-YYYY for the e-paper URL.
        e.g. 2026-04-13, islamabad -> https://e.thenews.com.pk/static_pages/4-13-2026/islamabad/thenews.pdf
        """
        year, month, day = date_str.split("-")
        date_part = f"{int(month)}-{int(day)}-{year}"   # strip leading zeros: 04 -> 4
        return f"{THENEWS_PDF_BASE}/{date_part}/{city}/thenews.pdf"

    @staticmethod
    def _download_file(url: str, dest: str) -> None:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Fix 1: Check Content-Type
            content_type = resp.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                raise ValueError("Server returned HTML instead of PDF (likely an error page).")

            data = resp.read()
            # Fix 2: Validate PDF magic bytes
            if not data.startswith(b"%PDF"):
                preview = data[:50].decode('ascii', errors='ignore')
                raise ValueError(f"Response is not a valid PDF. Magic bytes missing. Got: {preview!r}")

            with open(dest, "wb") as f:
                f.write(data)

    @staticmethod
    async def _download_city(date_str: str, city: str, target_dir: str) -> str | None:
        url = TheNewsService._build_pdf_url(date_str, city)
        dest = os.path.join(target_dir, f"{city}_{date_str}.pdf")
        
        if os.path.exists(dest):
            logger.info(f"[thenews/{city}] PDF already exists at {dest}")
            return dest

        logger.info(f"[thenews/{city}] GET {url}")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, TheNewsService._download_file, url, dest)
            size_kb = os.path.getsize(dest) // 1024
            logger.info(f"[thenews/{city}] ✓ Downloaded {size_kb} KB -> {dest}")
            return dest
        except urllib.error.HTTPError as e:
            logger.error(f"[thenews/{city}] ✗ HTTP {e.code} - PDF not available: {url}")
            return None
        except ValueError as e:
            logger.error(f"[thenews/{city}] ✗ Invalid PDF - {e} | URL: {url}")
            return None
        except Exception as e:
            logger.error(f"[thenews/{city}] ✗ Failed: {url} - {e}")
            return None

    @staticmethod
    async def process(date_str: str, cities: list[str] | None = None) -> list[PaperSuccessResponse]:
        target_cities = cities or THENEWS_CITIES
        target_dir = get_newspaper_dir("thenews")
        os.makedirs(target_dir, exist_ok=True)

        logger.info(f"[thenews] Downloading PDFs for {date_str}, cities={target_cities}")
        
        tasks = [
            TheNewsService._download_city(date_str, city, target_dir)
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
                    pages=0, # Pages count not known without parsing PDF
                    size_mb=round(size_mb, 2)
                ))
        
        return responses
