import os
import asyncio
import logging
import json
import tempfile
import shutil
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext

from app.core.config import (
    DAWN_SECTIONS, DAWN_USER_AGENT, DAWN_ARTICLE_CONCURRENCY,
    DAWN_SECTION_CONCURRENCY, DAWN_MAX_ARTICLES_PER_SECTION,
    DAWN_REQUEST_DELAY, PROJECT_ROOT
)
from app.utils.path_utils import get_newspaper_dir, get_pdf_path
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

# Resource types to block — we only need HTML
BLOCKED_RESOURCES = {"image", "stylesheet", "font", "media", "other"}

async def _block_resources(route):
    if route.request.resource_type in BLOCKED_RESOURCES:
        await route.abort()
    else:
        await route.continue_()

class DawnService:
    """
    Service for Dawn newspaper.
    Scrapes articles and generates a PDF.
    """

    @staticmethod
    async def _fetch_article(sem: asyncio.Semaphore, context: BrowserContext, url: str, section: str) -> dict | None:
        async with sem:
            await asyncio.sleep(DAWN_REQUEST_DELAY)
            page = await context.new_page()
            try:
                logger.info(f"[{section}] Fetching article: {url}")
                await page.route("**/*", _block_resources)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                soup = BeautifulSoup(await page.content(), "html.parser")

                title_elem = (
                    soup.select_one("h2.story__title a.story__link")
                    or soup.select_one("h1 a")
                    or soup.select_one("h1")
                )
                title = title_elem.get_text(strip=True) if title_elem else "Untitled"

                content_div = soup.select_one("div.story__content")
                if not content_div:
                    logger.warning(f"[{section}] No content div found: {url}")
                    return None

                content_html = "".join(str(p) for p in content_div.find_all("p"))
                logger.info(f"[{section}] ✓ Scraped: \"{title}\"")
                return {"title": title, "content": content_html}
            except Exception as e:
                logger.error(f"[{section}] ✗ ERROR while scraping {url}: {str(e)}")
                return None
            finally:
                logger.info(f"[{section}] Closing page for article: {url}")
                await page.close()

    @staticmethod
    async def _fetch_section_urls(sem: asyncio.Semaphore, context: BrowserContext, section: str, date_str: str) -> tuple[str, list[str]]:
        url = f"https://www.dawn.com/newspaper/{section}/{date_str}"
        async with sem:
            page = await context.new_page()
            try:
                logger.info(f"[{section}] Fetching section index: {url}")
                await page.route("**/*", _block_resources)
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                soup = BeautifulSoup(await page.content(), "html.parser")
                links = soup.select("a.story__link")
                urls = list(dict.fromkeys(
                    l["href"] for l in links
                    if l.get("href") and "dawn.com" in l["href"]
                ))[:DAWN_MAX_ARTICLES_PER_SECTION]
                if not urls:
                    logger.warning(f"[{section}] No article links found on index page")
                else:
                    logger.info(f"[{section}] Found {len(urls)} article(s)")
                return section, urls
            except Exception as e:
                logger.error(f"[{section}] ✗ Failed section index: {e}")
                return section, []
            finally:
                await page.close()

    @staticmethod
    async def scrape(date_str: str) -> str | None:
        logger.info(f"Starting Dawn scrape for date: {date_str}")
        article_sem = asyncio.Semaphore(DAWN_ARTICLE_CONCURRENCY)
        section_sem = asyncio.Semaphore(DAWN_SECTION_CONCURRENCY)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=DAWN_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )

            section_tasks = [
                DawnService._fetch_section_urls(section_sem, context, section, date_str)
                for section in DAWN_SECTIONS
            ]
            section_results = await asyncio.gather(*section_tasks)

            tagged_tasks = []
            for section_name, urls in section_results:
                for url in urls:
                    tagged_tasks.append(
                        (section_name, DawnService._fetch_article(article_sem, context, url, section_name))
                    )

            if not tagged_tasks:
                logger.error("No articles found across all sections.")
                await browser.close()
                return None

            total = len(tagged_tasks)
            logger.info(f"Starting parallel fetch of {total} articles...")
            
            section_names, coros = zip(*tagged_tasks)
            articles = await asyncio.gather(*coros)
            
            succeeded = sum(1 for a in articles if a is not None)
            logger.info(f"Article fetch complete — {succeeded}/{total} succeeded")
            
            await browser.close()

        sections_map = {s: [] for s in DAWN_SECTIONS}
        for section_name, article in zip(section_names, articles):
            if article:
                sections_map[section_name].append(article)

        # Improved sorting/titling to match PDFService expectations
        ordered_sections = []
        # Ensure 'front-page' is first
        if "front-page" in sections_map and sections_map["front-page"]:
            ordered_sections.append({
                "title": "Front Page",
                "articles": sections_map.pop("front-page")
            })
        
        # Add others
        for section in DAWN_SECTIONS:
            if section in sections_map and sections_map[section]:
                ordered_sections.append({
                    "title": section.replace("-", " ").title(),
                    "articles": sections_map.pop(section)
                })
        
        # Any leftovers
        for section, arts in sections_map.items():
            if arts:
                ordered_sections.append({
                    "title": section.replace("-", " ").title(),
                    "articles": arts
                })

        if not ordered_sections:
            return None

        sections_data = ordered_sections

        tmp_dir = tempfile.mkdtemp(prefix=f"dawn_{date_str}_")
        json_path = os.path.join(tmp_dir, "content.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sections_data, f)
        
        return json_path

    @staticmethod
    async def process(date_str: str):
        pdf_path = get_pdf_path("dawn", date_str)
        if os.path.exists(pdf_path):
            return PDFService._build_response("dawn", date_str, pdf_path, cached=True)

        json_path = await DawnService.scrape(date_str)
        if not json_path:
            raise ValueError(f"No content found for Dawn on {date_str}")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                sections_data = json.load(f)
            
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            PDFService._build_pdf(sections_data, pdf_path, "dawn", date_str)
            return PDFService._build_response("dawn", date_str, pdf_path)
        finally:
            shutil.rmtree(os.path.dirname(json_path), ignore_errors=True)
