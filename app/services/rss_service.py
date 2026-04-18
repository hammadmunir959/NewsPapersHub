import feedparser
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from app.core.config import DAWN_RSS_FEEDS

logger = logging.getLogger(__name__)

# Pakistan Standard Time offset (UTC+5)
PKT = timezone(timedelta(hours=5))


class RSSService:
    """
    Service to fetch and parse RSS feeds.
    Extracts articles with metadata including images and categories.
    """

    @staticmethod
    def _parse_pub_date(entry: dict) -> Optional[datetime]:
        """
        Parse the publication date from an RSS entry.

        feedparser auto-converts timezone-aware dates (e.g. +0500) to UTC
        in `published_parsed`. We convert back to PKT for date comparison.
        Falls back to raw string parsing if `published_parsed` is absent.
        """
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            # feedparser gives us UTC (it strips the original +0500 offset)
            utc_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            return utc_dt.astimezone(PKT)

        # Fallback: parse the raw pubDate string directly
        pub_str = entry.get("published", "")
        if not pub_str:
            return None

        try:
            # Dawn format: "Sat, 18 Apr 2026 19:20:10 +0500"
            dt = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.astimezone(PKT)
        except ValueError:
            pass

        # Last resort: extract just the date portion "18 Apr 2026"
        try:
            parts = pub_str.split()
            dt = datetime.strptime(" ".join(parts[1:4]), "%d %b %Y")
            return dt.replace(tzinfo=PKT)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _extract_image_url(entry: dict) -> Optional[str]:
        """Extract the best available image URL from the RSS entry."""
        # Try media:content first (full-size image)
        media_content = entry.get("media_content", [])
        if media_content:
            return media_content[0].get("url")

        # Fallback to media:thumbnail
        media_thumb = entry.get("media_thumbnail", [])
        if media_thumb:
            return media_thumb[0].get("url")

        return None

    @staticmethod
    def _extract_category(entry: dict, fallback: str = "") -> str:
        """Extract the category tag from the RSS entry."""
        tags = entry.get("tags", [])
        if tags:
            return tags[0].get("term", fallback)
        return fallback

    @staticmethod
    def fetch_articles(
        feeds: Dict[str, str] = DAWN_RSS_FEEDS,
        date_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch articles from multiple RSS feeds and return a deduplicated list.

        :param feeds: Dictionary mapping section names to feed URLs.
        :param date_filter: Date string in 'YYYY-MM-DD' format.
                            If None, today's date (PKT) is used.
        :returns: List of article dicts with keys: title, url, summary,
                  section, category, published, guid, image_url.
        """
        if date_filter is None:
            date_filter = datetime.now(PKT).strftime("%Y-%m-%d")

        all_articles: List[Dict] = []
        seen_urls: set = set()

        for section, feed_url in feeds.items():
            try:
                logger.info(f"Fetching RSS feed for section '{section}': {feed_url}")
                feed = feedparser.parse(feed_url)

                section_count = 0
                for entry in feed.entries:
                    article_url = entry.link
                    if article_url in seen_urls:
                        continue

                    # ── Date filtering ───────────────────────────
                    pub_dt = RSSService._parse_pub_date(entry)
                    if pub_dt:
                        if pub_dt.strftime("%Y-%m-%d") != date_filter:
                            continue
                    else:
                        logger.warning(
                            f"[{section}] Could not parse date for: {article_url}"
                        )
                        continue

                    # ── Build article dict ────────────────────────
                    article = {
                        "title": entry.get("title", "Untitled"),
                        "url": article_url,
                        "summary": entry.get("summary", ""),
                        "section": section,
                        "category": RSSService._extract_category(entry, fallback=section),
                        "published": entry.get("published", ""),
                        "guid": entry.get("id", article_url),
                        "image_url": RSSService._extract_image_url(entry),
                    }

                    all_articles.append(article)
                    seen_urls.add(article_url)
                    section_count += 1

                logger.info(
                    f"[{section}] {section_count} articles matched {date_filter} "
                    f"(out of {len(feed.entries)} entries)"
                )

            except Exception as e:
                logger.error(f"[{section}] Failed to fetch RSS feed: {e}")

        logger.info(f"Total unique articles for {date_filter}: {len(all_articles)}")
        return all_articles
