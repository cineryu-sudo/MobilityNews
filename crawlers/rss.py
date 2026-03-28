"""
RSS feed crawlers using feedparser.
"""

import feedparser
from datetime import datetime, date
import logging
from typing import List

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE, NEWS_SOURCES

logger = logging.getLogger(__name__)


class RSSBaseCrawler(BaseCrawler):
    """Base crawler for RSS feeds."""
    
    def __init__(self, source_name: str, language: str = "en"):
        # Fetch base url from config
        base_url = NEWS_SOURCES.get(source_name, "")
        super().__init__(source_name, base_url, language)
        
    def fetch(self) -> List[Article]:
        """Fetch articles from an RSS feed using feedparser."""
        articles = []
        try:
            feed = feedparser.parse(self.base_url)
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                
                # Parse published date
                published_date = None
                if "published_parsed" in entry and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6]).date()
                elif "updated_parsed" in entry and entry.updated_parsed:
                    published_date = datetime(*entry.updated_parsed[:6]).date()
                
                if title and url:
                    article = self._create_article(title=title, url=url, published_date=published_date)
                    articles.append(article)
                    
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to parse RSS feed: {e}")
            
        return articles


class TelematicsWireCrawler(RSSBaseCrawler):
    def __init__(self):
        super().__init__("telematics_wire", language="en")


class ZDNetKoreaCrawler(RSSBaseCrawler):
    def __init__(self):
        super().__init__("zdnet_korea", language="ko")


class FleetOwnerCrawler(RSSBaseCrawler):
    def __init__(self):
        super().__init__("fleetowner", language="en")
