"""
The Verge Transportation section crawler.
"""

from typing import List
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class TheVergeCrawler(BaseCrawler):
    """Crawler for The Verge Transportation section."""
    
    def __init__(self):
        super().__init__(
            source_name="The Verge",
            base_url="https://www.theverge.com",
            language="en"
        )
    
    def fetch(self) -> List[Article]:
        """Fetch articles from The Verge Transportation section."""
        url = f"{self.base_url}/transportation"
        soup = self._get_soup(url)
        
        if not soup:
            return []
        
        articles = []
        seen_urls = set()
        
        # The Verge uses links with /transportation/ or /20 in the path
        all_links = soup.select("a[href*='/transportation/'], a[href*='/20']")
        
        for link in all_links:
            try:
                href = link.get("href", "")
                
                # Skip invalid or duplicate URLs
                if not href or href in seen_urls:
                    continue
                if "/authors/" in href or "/archives/" in href:
                    continue
                    
                # Get title from link text
                title = link.get_text(strip=True)
                
                # Skip navigation links and short titles
                if not title or len(title) < 20:
                    continue
                
                # Make URL absolute if needed
                if href.startswith("/"):
                    href = f"{self.base_url}{href}"
                
                seen_urls.add(href)
                articles.append(self._create_article(title, href))
                
                if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                    break
                    
            except Exception as e:
                logger.warning(f"[The Verge] Failed to parse article: {e}")
                continue
        
        logger.info(f"[The Verge] Fetched {len(articles)} articles")
        return articles
