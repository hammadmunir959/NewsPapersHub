import feedparser
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Callable
from app.core.config import DAWN_RSS_FEEDS

logger = logging.getLogger(__name__)

PKT = timezone(timedelta(hours=5))

DAWN_RSS_CONFIG = {
    "feeds": {
        "home":           "https://www.dawn.com/feeds/home",
        "latest-news":    "https://www.dawn.com/feeds/latest-news",
        "pakistan":       "https://www.dawn.com/feeds/pakistan",
        "world":          "https://www.dawn.com/feeds/world",
        "business":       "https://www.dawn.com/feeds/business",
        "opinion":        "https://www.dawn.com/feeds/opinion",
        "sport":          "https://www.dawn.com/feeds/sport",
        "magazines":      "https://www.dawn.com/feeds/magazines",
        "tech":           "https://www.dawn.com/feeds/tech",
        "prism":          "https://www.dawn.com/feeds/prism",
    },
    "timezone": PKT,
}


class RSSArticleFetcher:
    """
    Generic RSS article fetcher. Configuration driven – works for any newspaper.

    Usage:
        config = {
            "feeds": {"home": "https://...rss", "world": "https://...rss"},
            "timezone": timezone(timedelta(hours=5)),      # source timezone
            "date_parser": None,                           # custom parser (optional)
            "image_extractor": None,
            "category_extractor": None,
        }
        fetcher = RSSArticleFetcher(config)
        articles = fetcher.fetch(date_filter="2026-04-28")
    """

    def __init__(self, config: dict):
        # Validate mandatory feeds
        self.feeds = config.get("feeds", {})
        if not self.feeds:
            raise ValueError("Config must contain a 'feeds' dict (section → url)")

        self.timezone = config.get("timezone", timezone.utc)
        self.date_parser = config.get("date_parser")          # Callable(entry) -> datetime|None
        self.image_extractor = config.get("image_extractor")
        self.category_extractor = config.get("category_extractor")
        self.max_per_feed = config.get("max_articles_per_feed")

    # ----------------------------------------------------------------
    # Default helpers – can be overridden via config
    # ----------------------------------------------------------------
    def _default_parse_date(self, entry: dict) -> Optional[datetime]:
        """Try feedparser's structured time, then common string formats."""
        # 1. feedparser's parsed time (UTC)
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            try:
                utc_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                return utc_dt.astimezone(self.timezone)
            except Exception:
                pass

        pub_str = entry.get("published", "")
        if not pub_str:
            return None

        # 2. Common RSS date strings with timezone offset
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",   # e.g., Sat, 18 Apr 2026 19:20:10 +0500
            "%a, %d %b %Y %H:%M:%S %Z",   # with timezone abbreviation
            "%Y-%m-%dT%H:%M:%S%z",        # ISO with offset
            "%Y-%m-%dT%H:%M:%SZ",         # UTC ISO
        ):
            try:
                dt = datetime.strptime(pub_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(self.timezone)
            except ValueError:
                continue

        # 3. Last resort – date only (e.g., "18 Apr 2026")
        try:
            parts = pub_str.split()
            if len(parts) >= 4:
                date_str = " ".join(parts[1:4])   # skip weekday
                naive_dt = datetime.strptime(date_str, "%d %b %Y")
                return naive_dt.replace(tzinfo=self.timezone)
        except (ValueError, IndexError):
            pass

        return None

    def _default_extract_image(self, entry: dict) -> Optional[str]:
        """Extract from media:content, media:thumbnail, or enclosures."""
        for field in ("media_content", "media_thumbnail"):
            media = entry.get(field, [])
            if media and "url" in media[0]:
                return media[0]["url"]

        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image/"):
                return enc.get("href")
        return None

    def _default_extract_category(self, entry: dict, fallback: str = "") -> str:
        tags = entry.get("tags", [])
        if tags:
            return tags[0].get("term", fallback)
        return fallback

    # ----------------------------------------------------------------
    # Main fetch method
    # ----------------------------------------------------------------
    def fetch(self, date_filter: Optional[str] = None) -> List[Dict]:
        """
        Fetch articles, deduplicate by URL, filter by date if given.
        If date_filter is None, no date filtering is performed.
        Returns a list of article dicts.
        """
        all_articles: List[Dict] = []
        seen_urls: set = set()

        for section, feed_url in self.feeds.items():
            try:
                logger.info("Fetching '%s' → %s", section, feed_url)
                feed = feedparser.parse(feed_url)

                entries = feed.entries
                if self.max_per_feed:
                    entries = entries[: self.max_per_feed]

                count = 0
                for entry in entries:
                    url = entry.get("link")
                    if not url or url in seen_urls:
                        continue

                    # ---- Date parsing and filtering ----
                    parser = self.date_parser or self._default_parse_date
                    pub_dt = parser(entry)

                    if date_filter and pub_dt:
                        if pub_dt.strftime("%Y-%m-%d") != date_filter:
                            continue
                    if date_filter and not pub_dt:
                        logger.debug("Skipping '%s' – unparseable date", url)
                        continue

                    # ---- Build article dictionary ----
                    article = {
                        "title": entry.get("title", "Untitled"),
                        "url": url,
                        "summary": entry.get("summary", ""),
                        "section": section,
                        "published": entry.get("published", ""),
                        "guid": entry.get("id", url),
                    }

                    img_ext = self.image_extractor or self._default_extract_image
                    article["image_url"] = img_ext(entry)

                    cat_ext = self.category_extractor or self._default_extract_category
                    article["category"] = cat_ext(entry, fallback=section)

                    all_articles.append(article)
                    seen_urls.add(url)
                    count += 1

                logger.info(
                    "[%s] %d articles matched (total %d entries in feed)",
                    section, count, len(feed.entries)
                )

            except Exception as exc:
                logger.exception("Error processing feed '%s': %s", section, exc)

        logger.info("Total unique articles collected: %d", len(all_articles))
        return all_articles

class RSSService:
    """
    Service layer to provide a simple interface for fetching articles.
    Maintains backward compatibility with the static method pattern.
    """
    @staticmethod
    def fetch_articles(feeds=None, date_filter=None, timezone=None, **kwargs):
        config = {
            "feeds": feeds or DAWN_RSS_FEEDS,
            "timezone": timezone or PKT,
            **kwargs
        }
        return RSSArticleFetcher(config).fetch(date_filter=date_filter)