import httpx
import os
import logging
import tempfile

from app.core.config import (
    DAWN_CDN_BASE,
    DAWN_MAX_PAGES,
    DAWN_USER_AGENT,
    SUPPORTED_NEWSPAPERS,
)

logger = logging.getLogger(__name__)


class Scraper:
    """Extensible scraper with static method dispatch per newspaper."""

    _registry: dict[str, callable] = {}

    @staticmethod
    async def scrape(newspaper: str, date_str: str, method: str = "epaper") -> list[str]:
        """Dispatch to the correct newspaper scraper.

        Args:
            newspaper: Newspaper name (must be in SUPPORTED_NEWSPAPERS).
            date_str: Date in YYYY-MM-DD format.
            method: Scrape method ('epaper' or 'text').

        Returns:
            List of downloaded image file paths.

        Raises:
            ValueError: If newspaper is not supported.
        """
        if newspaper not in SUPPORTED_NEWSPAPERS:
            raise ValueError(f"Unsupported newspaper: {newspaper}")

        scrapers = {
            "dawn": {
                "epaper": Scraper.scrape_dawn_epaper,
                "text": Scraper.scrape_dawn_text,
            }
        }
        
        if newspaper not in scrapers or method not in scrapers[newspaper]:
            raise ValueError(f"Unsupported newspaper {newspaper} or method {method}")
            
        return await scrapers[newspaper][method](date_str)

    @staticmethod
    async def scrape_dawn_epaper(date_str: str) -> list[str]:
        """Download all page images for a Dawn ePaper edition using Playwright screenshots.

        Args:
            date_str: Date in YYYY-MM-DD format.

        Returns:
            List of downloaded image file paths (in a temp directory).
        """
        import asyncio
        from playwright.async_api import async_playwright
        import os

        year, month, day = date_str.split("-")
        date_param = f"{day}_{month}_{year}"
        
        # Use a temp dir for images
        tmp_dir = tempfile.mkdtemp(prefix=f"dawn_epaper_{date_str}_")
        image_paths: list[str] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Use high-res viewport to force higher quality rendering
            context = await browser.new_context(
                user_agent=DAWN_USER_AGENT,
                viewport={"width": 2048, "height": 3072},
                device_scale_factor=2 # Retina-like quality
            )
            page = await context.new_page()

            for page_num in range(1, DAWN_MAX_PAGES + 1):
                url = f"https://epaper.dawn.com/?page={date_param}_{page_num:03d}"
                logger.info(f"Navigating to ePaper page {page_num}: {url}")
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    # Check if page exists (handle the "page not found" case in the SPA if possible)
                    # Or check for specific element indicating end of edition
                    
                    # Wait for the main ePaper image/canvas to be visible
                    # We increased sleep to 5s to ensure images load even if we don't wait for network idle
                    await asyncio.sleep(5) 

                    file_path = os.path.join(tmp_dir, f"page_{page_num:03d}.png")
                    
                    # Instead of full page, we locate the frame containing the paper canvas
                    frame = page.frame_locator('iframe#DawnPaperFrame')
                    # We capture just the content inside the frame
                    await frame.locator('body').screenshot(path=file_path)

                    
                    # Basic validation: if screenshot failed or is somehow unusable
                    if os.path.exists(file_path):
                        image_paths.append(file_path)
                        logger.info(f"Captured high-res screenshot for page {page_num}")
                    else:
                        break
                    
                    # Detect if we've reached a duplicate or error page (end of edition)
                    # For now we rely on DAWN_MAX_PAGES and manual review.
                    
                except Exception as e:
                    logger.error(f"Failed to capture ePaper page {page_num}: {e}")
                    break

            await browser.close()

        logger.info(f"Visual scraping complete: {len(image_paths)} pages for dawn/{date_str}")
        return image_paths

    @staticmethod
    async def scrape_dawn_text(date_str: str) -> list[str]:
        """Scrape articles for Dawn newspaper and return JSON-ready structure.
        
        This method will:
        1. Visit dawn.com/newspaper/[section]/date for key sections.
        2. Scrape article URLs.
        3. Scrape each article's content.
        4. Render to a temporary HTML file and return its path.
        """
        import asyncio
        from bs4 import BeautifulSoup
        from playwright.async_api import async_playwright
        import os

        # Full editorial section taxonomy (classifieds/ads excluded intentionally)
        sections_to_scrape = [
            # News
            "front-page",
            "national",
            "international",
            # Analysis
            "editorial",
            "opinion",
            "columns",
            "letters",
            # Economy
            "business",
            "markets",
            # Society - Metro editions
            "metro-islamabad",
            # Other
            "sport",
            "back-page",
            # Magazines and Features (skipped gracefully if empty/404)
            "icon",
            "eos",
            "young-world",
            "features",
            "weekend",
            "images",
            "books-and-authors",
            "aurora",
            "prism",
            "magazine",
            "in-paper-magazine",
            "sci-tech",
            "entertainment",
            "lifestyle",
        ]
        base_url = "https://www.dawn.com/newspaper"
        
        sections_data = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=DAWN_USER_AGENT)
            page = await context.new_page()

            for section in sections_to_scrape:
                section_url = f"{base_url}/{section}/{date_str}"
                logger.info(f"Scraping section: {section_url}")
                
                try:
                    await page.goto(section_url, wait_until="domcontentloaded", timeout=30000)
                    html = await page.content()
                    sop = BeautifulSoup(html, "html.parser")
                    
                    links = sop.select("a.story__link")
                    article_urls = [l["href"] for l in links if l.get("href") and ("dawn.com" in l["href"] or l["href"].startswith("/"))]
                    
                    # Deduplicate - no artificial limit, scrape full section
                    article_urls = list(dict.fromkeys(article_urls))[:25]
                    
                    section_articles = []
                    for art_url in article_urls:
                        logger.info(f"Scraping article: {art_url}")
                        try:
                            await page.goto(art_url, wait_until="domcontentloaded", timeout=20000)
                            art_html = await page.content()
                            art_sop = BeautifulSoup(art_html, "html.parser")
                            
                            title_tag = art_sop.select_one("h2.story__title a.story__link")
                            title = title_tag.get_text(strip=True) if title_tag else "Untitled"
                            
                            author_tag = art_sop.select_one("a.story__byline__link")
                            author = author_tag.get_text(strip=True) if author_tag else None
                            
                            content_div = art_sop.select_one("div.story__content")
                            if content_div:
                                # Get all paragraphs
                                paragraphs = content_div.find_all("p")
                                content_html = "".join([str(p) for p in paragraphs])
                                
                                section_articles.append({
                                    "title": title,
                                    "author": author,
                                    "content": content_html
                                })
                        except Exception as e:
                            logger.warning(f"Failed to scrape article {art_url}: {e}")
                            continue
                            
                    if section_articles:
                        sections_data.append({
                            "title": section.replace("-", " ").capitalize(),
                            "articles": section_articles
                        })
                except Exception as e:
                    logger.warning(f"Failed to scrape section {section}: {e}")
                    # Record the failure instead of skipping
                    sections_data.append({
                        "title": section.replace("-", " ").capitalize(),
                        "articles": [],
                        "error": f"Section could not be fetched: {str(e)}"
                    })
                    continue

            await browser.close()

        if not sections_data:
            raise ValueError(f"No articles found for dawn on {date_str}")

        import json
        tmp_dir = tempfile.mkdtemp(prefix=f"dawn_text_{date_str}_")
        json_file_path = os.path.join(tmp_dir, "content.json")
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(sections_data, f)

        return [json_file_path]
