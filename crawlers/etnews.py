"""
전자신문 (ETNews) ICT/자동차 섹션 크롤러.
"""

from typing import List
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class ETNewsCrawler(BaseCrawler):
    """전자신문 ICT/자동차 섹션 크롤러."""
    
    def __init__(self):
        super().__init__(
            source_name="전자신문",
            base_url="https://www.etnews.com",
            language="ko"
        )
    
    def fetch(self) -> List[Article]:
        """전자신문에서 기사 수집."""
        url = f"{self.base_url}/news/section.html?id1=03"
        soup = self._get_soup(url)
        
        if not soup:
            return []
        
        articles = []
        seen_urls = set()
        
        # 전자신문 uses numeric article IDs in URLs like /20260209000093
        all_links = soup.select("a[href*='/20']")
        
        for link in all_links:
            try:
                href = link.get("href", "")
                
                # Skip invalid or duplicate URLs
                if not href or href in seen_urls:
                    continue
                    
                # Only etnews article URLs (numeric format)
                if "etnews.com" not in href and not href.startswith("/"):
                    continue
                
                # Get title from link text
                title = link.get_text(strip=True)
                
                # Skip navigation links and short titles
                if not title or len(title) < 10:
                    continue
                
                # Make URL absolute if needed
                if href.startswith("/"):
                    href = f"{self.base_url}{href}"
                
                seen_urls.add(href)
                articles.append(self._create_article(title, href))
                
                if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                    break
                    
            except Exception as e:
                logger.warning(f"[전자신문] 기사 파싱 실패: {e}")
                continue
        
        logger.info(f"[전자신문] {len(articles)}개 기사 수집")
        return articles
