"""
Hacker News API client for autonomous/mobility related stories.
"""

from typing import List
from datetime import date, datetime
import logging
import requests

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class HackerNewsCrawler(BaseCrawler):
    """Hacker News API client for autonomous driving stories."""
    
    def __init__(self):
        super().__init__(
            source_name="Hacker News",
            base_url="https://news.ycombinator.com",
            language="en"
        )
        self.api_url = "https://hn.algolia.com/api/v1/search_by_date"
    
    def fetch(self) -> List[Article]:
        """Fetch autonomous-related stories from Hacker News API."""
        articles = []
        
        # Search for mobility-related keywords
        queries = ["autonomous driving", "electric vehicle", "Tesla", "Waymo"]
        
        for query in queries:
            try:
                params = {
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": 5,
                }
                
                response = requests.get(
                    self.api_url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()
                data = response.json()
                
                for hit in data.get("hits", []):
                    title = hit.get("title", "")
                    url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"

                    # API의 created_at에서 날짜 추출 (예: "2026-03-04T12:00:00.000Z")
                    pub_date = None
                    created_at = hit.get("created_at", "")
                    if created_at:
                        try:
                            pub_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
                        except ValueError:
                            pass

                    if title and url:
                        # Avoid duplicates
                        if not any(a.url == url for a in articles):
                            articles.append(self._create_article(title, url, published_date=pub_date))
                            
            except requests.RequestException as e:
                logger.warning(f"[Hacker News] API request failed for '{query}': {e}")
                continue
        
        # Limit to max articles
        articles = articles[:MAX_ARTICLES_PER_SOURCE]
        logger.info(f"[Hacker News] Fetched {len(articles)} articles")
        return articles
