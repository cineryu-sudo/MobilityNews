"""
TechCrunch Transportation section crawler.
"""

from typing import List
from datetime import date
import re
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class TechCrunchCrawler(BaseCrawler):
    """Crawler for TechCrunch Transportation section."""
    
    def __init__(self):
        super().__init__(
            source_name="TechCrunch",
            base_url="https://techcrunch.com",
            language="en"
        )
    
    def _parse_date_from_url(self, url: str):
        """URL에서 날짜 추출. 예: /2026/03/04/ → date(2026, 3, 4)"""
        match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None
        return None

    def fetch(self) -> List[Article]:
        """Fetch articles from TechCrunch Transportation section."""
        url = f"{self.base_url}/category/transportation/"
        soup = self._get_soup(url)

        if not soup:
            return []

        articles = []
        seen_urls = set()

        # TechCrunch uses various link structures - find all links to articles
        all_links = soup.select("a[href*='/20']")

        for link in all_links:
            try:
                href = link.get("href", "")

                # Filter: only techcrunch.com articles with date in URL
                if not href or "techcrunch.com" not in href:
                    continue
                if "/category/" in href or "/tag/" in href or "/author/" in href:
                    continue
                if href in seen_urls:
                    continue

                # Get title from link text or nested elements
                title = link.get_text(strip=True)

                # Skip if title is too short (navigation links, etc.)
                if not title or len(title) < 15:
                    continue

                seen_urls.add(href)
                pub_date = self._parse_date_from_url(href)
                articles.append(self._create_article(title, href, published_date=pub_date))

                if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                    break

            except Exception as e:
                logger.warning(f"[TechCrunch] Failed to parse article: {e}")
                continue

        logger.info(f"[TechCrunch] Fetched {len(articles)} articles")
        return articles
