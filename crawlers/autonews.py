"""
Automotive News Mobility Technology section crawler.
"""

from typing import List
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class AutoNewsCrawler(BaseCrawler):
    """Crawler for Automotive News Mobility Technology section."""
    
    def __init__(self):
        super().__init__(
            source_name="Automotive News",
            base_url="https://www.autonews.com",
            language="en"
        )
    
    def fetch(self) -> List[Article]:
        """Fetch articles from Automotive News Mobility Technology section."""
        url = f"{self.base_url}/mobility-technology"
        soup = self._get_soup(url)
        
        if not soup:
            return []
        
        articles = []
        
        # Automotive News uses standard article cards
        article_elements = soup.select("article, div.article-item, div.card")
        
        for element in article_elements[:MAX_ARTICLES_PER_SOURCE * 2]:
            try:
                # Find title link
                title_link = element.select_one("h2 a, h3 a, a.headline, a[href*='/mobility']")
                
                if title_link:
                    title = title_link.get_text(strip=True)
                    href = title_link.get("href", "")
                    
                    if title and href and len(title) > 10:
                        articles.append(self._create_article(title, href))
                        
                        if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                            break
            except Exception as e:
                logger.warning(f"[Automotive News] Failed to parse article: {e}")
                continue
        
        logger.info(f"[Automotive News] Fetched {len(articles)} articles")
        return articles
