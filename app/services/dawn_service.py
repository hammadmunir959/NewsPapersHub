import os
import asyncio
import logging
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext

from app.core.config import (
    DAWN_USER_AGENT, DAWN_ARTICLE_CONCURRENCY,
    DAWN_REQUEST_DELAY, DAWN_RSS_FEEDS
)
from app.utils.path_utils import get_newspaper_dir, get_pdf_path
from app.services.rss_service import RSSService
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
    async def process(date_str: str):
        """
        Main entry point for Dawn newspaper PDF generation.
        Uses RSS feeds for article discovery and Playwright for content extraction.
        """
        logger.info(f"Starting Dawn process for date: {date_str} (RSS Method)")
        pdf_path = get_pdf_path("dawn", date_str)
        
        # 1. Check Cache
        if os.path.exists(pdf_path):
            logger.info(f"Returning cached PDF: {pdf_path}")
            return [PDFService._build_response("dawn", date_str, pdf_path, cached=True)]

        # 2. Discover Articles via RSS
        articles = RSSService.fetch_articles(DAWN_RSS_FEEDS, date_filter=date_str)
        if not articles:
            logger.warning(f"No RSS articles found for date {date_str}")
            # If no articles found for specific date, we can't proceed with generating that day's edition
            raise ValueError(f"No articles found in RSS feeds for {date_str}")

        logger.info(f"Found {len(articles)} articles in RSS. Starting content scrape...")

        # 3. Scrape Full Content using Playwright
        article_sem = asyncio.Semaphore(DAWN_ARTICLE_CONCURRENCY)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, channel="chrome")

            context = await browser.new_context(
                user_agent=DAWN_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )

            tasks = []
            for art in articles:
                tasks.append(
                    DawnService._fetch_article(article_sem, context, art["url"], art["section"])
                )
            
            scraped_contents = await asyncio.gather(*tasks)
            await browser.close()

        # 4. Group by section (with RSS summary fallback)
        sections_map = {}
        fallback_count = 0
        for original_art, scraped in zip(articles, scraped_contents):
            section = original_art["section"]
            if section not in sections_map:
                sections_map[section] = []

            if scraped:
                sections_map[section].append({
                    "title": scraped["title"],
                    "content": scraped["content"]
                })
            elif original_art.get("summary"):
                # Fallback: use the RSS summary when Playwright scraping fails
                logger.info(f"[{section}] Using RSS summary fallback for: {original_art['title']}")
                sections_map[section].append({
                    "title": original_art["title"],
                    "content": original_art["summary"]
                })
                fallback_count += 1
            else:
                logger.warning(f"[{section}] Dropped article (no content): {original_art['url']}")

        if fallback_count:
            logger.info(f"Used RSS summary fallback for {fallback_count} article(s)")

        # 5. Format for PDFService
        section_order = ["home", "latest-news", "pakistan", "world", "business", "opinion", "sport", "magazines", "tech", "prism"]
        
        sorted_sections = []
        # First add "home" if it exists
        if "home" in sections_map:
            sorted_sections.append(("home", sections_map.pop("home")))
        
        # Then add others in pre-defined order
        for s in section_order:
            if s in sections_map:
                sorted_sections.append((s, sections_map.pop(s)))
        
        # Then add any remaining
        for s, arts in sections_map.items():
            sorted_sections.append((s, arts))

        sections_data = [
            {
                "title": section.replace("-", " ").title() if section != "home" else "Front Page",
                "articles": arts
            }
            for section, arts in sorted_sections
        ]

        if not sections_data:
            raise ValueError(f"Failed to scrape any article content for {date_str}")

        # 6. Generate PDF
        logger.info(f"Triggering PDF generation at {pdf_path}")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        PDFService._build_pdf(sections_data, pdf_path, "dawn", date_str)
        
        return [PDFService._build_response("dawn", date_str, pdf_path)]
