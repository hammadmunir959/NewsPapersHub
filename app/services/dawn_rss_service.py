import os
import asyncio
import logging
import tempfile
import json
import shutil
from datetime import datetime
from playwright.async_api import async_playwright

from app.core.config import (
    DAWN_USER_AGENT, DAWN_ARTICLE_CONCURRENCY, DAWN_REQUEST_DELAY, 
    DAWN_RSS_FEEDS, PROJECT_ROOT
)
from app.utils.path_utils import get_pdf_path
from app.services.rss_service import RSSService
from app.services.dawn_service import DawnService, _block_resources
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

class DawnRSSService:
    """
    Orchestrator for Dawn RSS-based edition generation.
    """

    @staticmethod
    async def process(date_str: str):
        """
        Generate Dawn PDF based on RSS feeds for a specific date.
        """
        pdf_path = get_pdf_path("dawn", f"{date_str}_rss") # Distinct name for RSS edition
        
        # We don't cache RSS editions by default as feeds update
        # But for the purpose of this task, let's just generate it
        
        articles = RSSService.fetch_articles(DAWN_RSS_FEEDS, date_filter=date_str)
        logger.info(f"Step 1: RSS Fetch complete. Found {len(articles)} articles for {date_str}.")
        if not articles:
            logger.warning(f"No RSS articles found for date {date_str}")
            raise ValueError(f"No articles found in RSS feeds for {date_str}")

        logger.info(f"Step 2: Starting browser for article content scraping...")

        # Scraping full content for each article
        article_sem = asyncio.Semaphore(DAWN_ARTICLE_CONCURRENCY)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=DAWN_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )

            logger.info(f"Starting parallel fetch of {len(articles)} articles...")
            tasks = []
            for i, art in enumerate(articles):
                logger.info(f"Queueing article {i+1}/{len(articles)}: {art['title']} [{art['section']}]")
                tasks.append(
                    DawnService._fetch_article(article_sem, context, art["url"], art["section"])
                )
            
            scraped_contents = await asyncio.gather(*tasks)
            logger.info(f"Step 3: Scraping complete. Successfully scraped {sum(1 for s in scraped_contents if s)}/{len(articles)} articles.")
            await browser.close()

        # Group by section
        logger.info(f"Step 4: Grouping articles by section...")
        sections_map = {}
        for original_art, scraped in zip(articles, scraped_contents):
            if not scraped:
                continue
            
            section = original_art["section"]
            if section not in sections_map:
                sections_map[section] = []
            
            sections_map[section].append({
                "title": scraped["title"],
                "content": scraped["content"]
            })

        # Format for PDFService
        logger.info(f"Step 5: Formatting data for PDF generation...")
        # Sort sections to ensure "home" is always first for the FrontPage template
        section_order = ["home", "pakistan", "world", "business", "opinion", "sport", "magazines"]
        
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

        logger.info(f"Step 6: Triggering PDF generation at {pdf_path}")
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        PDFService._build_pdf(sections_data, pdf_path, "dawn", date_str)
        
        logger.info(f"Step 7: PDF generation complete!")
        return PDFService._build_response("dawn", f"{date_str}_rss", pdf_path)
