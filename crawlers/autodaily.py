"""
오토데일리 뉴스 크롤러.
"""

from typing import List
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class AutoDailyCrawler(BaseCrawler):
    """오토데일리 뉴스 크롤러."""
    
    def __init__(self):
        super().__init__(
            source_name="오토데일리",
            base_url="http://www.autodaily.co.kr",
            language="ko"
        )
    
    def fetch(self) -> List[Article]:
        """오토데일리에서 기사 수집."""
        url = f"{self.base_url}/news/articleList.html?sc_section_code=S1N1"
        soup = self._get_soup(url)
        
        if not soup:
            return []
        
        articles = []
        
        # 오토데일리는 표준 뉴스 리스트 구조
        article_elements = soup.select("div.list-block, li.article-list, ul.type2 li, div.article-list li")
        
        for element in article_elements[:MAX_ARTICLES_PER_SOURCE * 2]:
            try:
                # 제목 링크 찾기
                title_link = element.select_one("a.list-titles, h4 a, h3 a, a[href*='articleView']")
                
                if title_link:
                    title = title_link.get_text(strip=True)
                    href = title_link.get("href", "")
                    
                    if title and href and len(title) > 5:
                        articles.append(self._create_article(title, href))
                        
                        if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                            break
            except Exception as e:
                logger.warning(f"[오토데일리] 기사 파싱 실패: {e}")
                continue
        
        logger.info(f"[오토데일리] {len(articles)}개 기사 수집")
        return articles
