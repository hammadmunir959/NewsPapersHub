import os
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext

from app.core.config import (
    DAWN_USER_AGENT, DAWN_ARTICLE_CONCURRENCY,
    DAWN_REQUEST_DELAY, DAWN_RSS_FEEDS
)
from app.utils.path_utils import get_pdf_path
from app.services.rss_service import RSSService
from app.services.pdf_service import PDFService
from app.services.task_manager_service import task_manager
from app.models.schemas import TaskState

logger = logging.getLogger(__name__)

# Extended list of resource types to block – no images, styles, fonts, media, analytics
BLOCKED_RESOURCE_TYPES = {"image", "stylesheet", "font", "media", "other", "script", "xhr", "fetch"}

# Custom exception for article retrieval failures
class ArticleFetchError(Exception):
    pass

class DawnScraper:
    """Handles Playwright-based content extraction for Dawn articles."""

    def __init__(self, concurrency: int = DAWN_ARTICLE_CONCURRENCY, delay: float = DAWN_REQUEST_DELAY):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay = delay

    async def _block_unnecessary(self, route):
        """Route handler to block non-HTML resources."""
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    async def fetch_article(self, context: BrowserContext, url: str, section: str) -> Optional[Dict[str, str]]:
        """
        Fetch a single article, applying concurrency limit and delay.
        """
        async with self.semaphore:
            await asyncio.sleep(self.delay)
            page = await context.new_page()
            try:
                logger.info(f"[{section}] Fetching: {url}")
                await page.route("**/*", self._block_unnecessary)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                html_content = await page.content()
                
                # Offload CPU-bound parsing to a thread executor
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, self._parse_article_html, html_content, url, section
                )
            
            except Exception:
                logger.error(f"[{section}] ✗ ERROR scraping {url}", exc_info=True)
                return None
            finally:
                await page.close()

    def _parse_article_html(self, html: str, url: str, section: str) -> Optional[Dict[str, str]]:
        """CPU-bound BeautifulSoup parsing (runs in executor)."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Title extraction
        title_elem = (
            soup.select_one("h2.story__title a.story__link") or
            soup.select_one("h1 a") or
            soup.select_one("h1")
        )
        title = title_elem.get_text(strip=True) if title_elem else "Untitled"
        
        # Content extraction
        content_div = soup.select_one("div.story__content")
        if not content_div:
            logger.warning(f"[{section}] No content div: {url}")
            return None
        
        content_html = "".join(str(p) for p in content_div.find_all("p"))
        logger.info(f"[{section}] ✓ Scraped: \"{title}\"")
        return {"title": title, "content": content_html}

    async def scrape_all(self, articles: List[Dict[str, str]], context: BrowserContext) -> List[Optional[Dict[str, str]]]:
        """Scrape a list of articles concurrently, preserving order."""
        tasks = [
            self.fetch_article(context, art["url"], art["section"])
            for art in articles
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)  # exceptions become None inside fetch_article

class DawnService:
    """
    Service for Dawn newspaper PDF generation.
    Uses RSS discovery + Playwright scraping + PDF composition.
    """

    def __init__(self):
        self.scraper = DawnScraper(
            concurrency=DAWN_ARTICLE_CONCURRENCY,
            delay=DAWN_REQUEST_DELAY
        )

    async def process(self, date_str: str, task_id: Optional[str] = None) -> dict:
        """
        Main entry point. Returns a response dict (not a list).
        """
        logger.info(f"Starting Dawn process for {date_str} (RSS method)")
        if task_id:
            await task_manager.publish(task_id, TaskState.DISCOVERING, 5,
                                       f"Starting Dawn process for {date_str}")
        
        pdf_path = get_pdf_path("dawn", date_str)
        
        # 1. Check local cache
        if os.path.exists(pdf_path):
            logger.info(f"Returning cached PDF: {pdf_path}")
            return PDFService._build_response("dawn", date_str, pdf_path)
        
        # 2. Discover articles via RSS (run blocking code in executor)
        if task_id:
            await task_manager.publish(task_id, TaskState.DISCOVERING, 10,
                                       "Discovering articles via RSS feeds...")
        loop = asyncio.get_running_loop()
        articles = await loop.run_in_executor(
            None, lambda: RSSService.fetch_articles(DAWN_RSS_FEEDS, date_filter=date_str)
        )
        if not articles:
            raise ValueError(f"No articles found in RSS feeds for {date_str}")
        
        total_arts = len(articles)
        logger.info(f"Found {total_arts} RSS articles")
        if task_id:
            await task_manager.publish(task_id, TaskState.DOWNLOADING, 20,
                                       f"Scraping {total_arts} articles...")
        
        # 3. Scrape full content with Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, channel="chrome")
            try:
                context = await browser.new_context(
                    user_agent=DAWN_USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                )
                # Run scraping and report progress in chunks
                scraped_contents = await self._run_scraping_with_progress(
                    context, articles, task_id, total_arts
                )
            finally:
                await browser.close()
        
        # 4. Build sections with fallback to RSS summaries
        sections_map, fallback_count = self._group_articles_by_section(articles, scraped_contents)
        if fallback_count:
            logger.info(f"Used RSS summary fallback for {fallback_count} article(s)")
        
        # 5. Order sections
        ordered_sections = self._order_sections(sections_map)
        sections_data = [
            {
                "title": section.replace("-", " ").title() if section != "home" else "Front Page",
                "articles": arts
            }
            for section, arts in ordered_sections
        ]
        if not sections_data:
            raise ValueError(f"Failed to scrape any article content for {date_str}")
        
        # 6. Generate PDF (blocking code in executor)
        if task_id:
            await task_manager.publish(task_id, TaskState.BUILDING_PDF, 85,
                                       "Formatting and generating final PDF...")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        await loop.run_in_executor(
            None, PDFService._build_pdf, sections_data, pdf_path, "dawn", date_str
        )
        
        if task_id:
            await task_manager.publish(task_id, TaskState.COMPLETED, 100,
                                       "Successfully generated Dawn PDF!")
        
        return PDFService._build_response("dawn", date_str, pdf_path)

    async def _run_scraping_with_progress(self, context, articles, task_id, total):
        """Scrape articles and update progress."""
        async def _wrap_task(i, t):
            res = await t
            return i, res

        tasks = [
            _wrap_task(i, self.scraper.fetch_article(context, art["url"], art["section"]))
            for i, art in enumerate(articles)
        ]
        
        results = [None] * total
        completed_count = 0
        for coro in asyncio.as_completed(tasks):
            idx, result = await coro
            results[idx] = result
            completed_count += 1
            
            if task_id and (completed_count == total or completed_count % max(1, total // 5) == 0):
                pct = 20 + int(60 * (completed_count / total))
                await task_manager.publish(
                    task_id, TaskState.DOWNLOADING, pct,
                    f"Scraped {completed_count}/{total} articles..."
                )
        return results

    def _group_articles_by_section(self, articles, scraped_contents):
        """Combine articles with scraped content; fall back to RSS summary."""
        sections_map: Dict[str, List[Dict[str, str]]] = {}
        fallback_count = 0
        for art, scraped in zip(articles, scraped_contents):
            section = art["section"]
            sections_map.setdefault(section, [])
            if scraped:
                sections_map[section].append({
                    "title": scraped["title"],
                    "content": scraped["content"]
                })
            elif art.get("summary"):
                logger.info(f"[{section}] Using RSS summary for: {art['title']}")
                sections_map[section].append({
                    "title": art["title"],
                    "content": art["summary"]
                })
                fallback_count += 1
            else:
                logger.warning(f"[{section}] Dropped article (no content): {art['url']}")
        return sections_map, fallback_count

    def _order_sections(self, sections_map: Dict[str, List]) -> List[Tuple[str, List]]:
        """Order sections: home first, then a predefined list, then the rest."""
        preferred = ["home", "latest-news", "pakistan", "world", "business",
                     "opinion", "sport", "magazines", "tech", "prism"]
        ordered = []
        # Home always first if present
        if "home" in sections_map:
            ordered.append(("home", sections_map.pop("home")))
        # Add known sections in order
        for s in preferred:
            if s in sections_map:
                ordered.append((s, sections_map.pop(s)))
        # Remaining sections alphabetically for consistency
        for s in sorted(sections_map.keys()):
            ordered.append((s, sections_map[s]))
        return ordered