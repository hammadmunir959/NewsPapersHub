import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from app.core.config import DAWN_RSS_FEEDS

logger = logging.getLogger(__name__)

class RSSService:
    """
    Service to fetch and parse RSS feeds.
    """

    @staticmethod
    def fetch_articles(feeds: Dict[str, str] = DAWN_RSS_FEEDS, date_filter: str = None) -> List[Dict]:
        """
        Fetch articles from multiple RSS feeds and return a deduplicated list.
        :param feeds: Dictionary of feed names and URLs.
        :param date_filter: Date string in 'YYYY-MM-DD' format to filter articles. 
                           If None, today's date is used.
        """
        if date_filter is None:
            date_filter = datetime.now().strftime("%Y-%m-%d")
        
        all_articles = []
        seen_urls = set()

        for section, url in feeds.items():
            try:
                logger.info(f"Fetching RSS feed for section {section}: {url}")
                feed = feedparser.parse(url)
                
                for entry in feed.entries:
                    # Deduplicate by URL
                    url = entry.link
                    if url in seen_urls:
                        continue
                    
                    # Filter by date
                    # Dawn RSS dates are usually like "Tue, 14 Apr 2026 01:23:45 +0500"
                    # feedparser.published_parsed is in UTC.
                    # We need to convert it to Pakistan time (UTC+5)
                    published_parsed = entry.get("published_parsed")
                    if published_parsed:
                        # Convert UTC to Pakistan time (+5 hours)
                        utc_dt = datetime(*published_parsed[:6])
                        local_dt = utc_dt + timedelta(hours=5)
                        pub_date = local_dt.strftime("%Y-%m-%d")
                        
                        if pub_date != date_filter:
                            continue
                    else:
                        # Fallback parsing for the raw string if published_parsed fails
                        pub_str = entry.get("published", "")
                        try:
                            # Try to parse "Tue, 14 Apr 2026 01:23:45 +0500"
                            # We extract the date part "14 Apr 2026"
                            dt = datetime.strptime(" ".join(pub_str.split()[1:4]), "%d %b %Y")
                            if dt.strftime("%Y-%m-%d") != date_filter:
                                continue
                        except Exception:
                            logger.warning(f"Could not parse date for article: {url}")
                            continue

                    article = {
                        "title": entry.title,
                        "url": entry.link,
                        "summary": entry.get("summary", ""),
                        "section": section,
                        "category": entry.get("category", section),
                        "published": entry.get("published", ""),
                        "guid": entry.get("id", entry.link)
                    }
                    
                    all_articles.append(article)
                    seen_urls.add(url)
                    
                logger.info(f"Found {len(feed.entries)} entries in {section}, {len(all_articles)} total unique for {date_filter}")
                
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {section}: {e}")

        return all_articles
