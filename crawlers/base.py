"""
Base crawler class and Article dataclass.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date
import requests
from bs4 import BeautifulSoup
import time
import logging

from config import ARTICLE_CONTENT_MAX_CHARS, REQUEST_DELAY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents a news article."""
    title: str
    url: str
    source: str
    language: str  # "en" or "ko"
    published_date: Optional[date] = field(default=None)  # 기사 발행일 (없으면 None)
    content: Optional[str] = field(default=None)  # 기사 본문 (요약용, 최대 ARTICLE_CONTENT_MAX_CHARS자)

    def __repr__(self):
        return f"Article(title='{self.title[:50]}...', source='{self.source}')"


class BaseCrawler(ABC):
    """Abstract base class for all news crawlers."""
    
    def __init__(self, source_name: str, base_url: str, language: str = "en"):
        self.source_name = source_name
        self.base_url = base_url
        self.language = language
        self.last_error = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    def _get_soup(self, url: str) -> BeautifulSoup | None:
        """Fetch URL and return BeautifulSoup object."""
        try:
            self.last_error = ""
            time.sleep(REQUEST_DELAY)
            response = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            self.last_error = str(e)
            logger.error(f"[{self.source_name}] Failed to fetch {url}: {e}")
            return None
    
    def fetch_article_content(self, url: str, max_chars: int = ARTICLE_CONTENT_MAX_CHARS) -> str:
        """기사 URL에서 본문 텍스트를 추출한다 (최대 max_chars자).

        <p> 태그의 텍스트를 모아서 반환한다.
        실패 시 빈 문자열을 반환한다.
        """
        soup = self._get_soup(url)
        if not soup:
            return ""

        # 페이지에 <article>이 여러 개면 메뉴·카드일 수 있으므로 문단이 가장 긴 것을 쓰고,
        # 문단이 있는 <article>이 없으면 페이지 전체에서 추출한다.
        candidates = [self._paragraph_text(tag) for tag in soup.find_all("article")]
        text = max(candidates, key=len, default="") or self._paragraph_text(soup)
        return text[:max_chars]

    @staticmethod
    def _paragraph_text(container) -> str:
        """컨테이너 안 <p> 태그의 텍스트를 이어 붙인다."""
        paragraphs = container.find_all("p")
        return " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

    @abstractmethod
    def fetch(self) -> List[Article]:
        """Fetch articles from the news source. Must be implemented by subclasses."""
        pass
    
    def _create_article(self, title: str, url: str, published_date: Optional[date] = None) -> Article:
        """Create an Article instance with common attributes."""
        # Ensure absolute URL
        if not url.startswith("http"):
            url = self.base_url.rstrip("/") + "/" + url.lstrip("/")

        return Article(
            title=title.strip(),
            url=url,
            source=self.source_name,
            language=self.language,
            published_date=published_date,
        )


class ContentFetcher(BaseCrawler):
    """목록 수집 없이 기사 본문만 가져오는 용도의 크롤러."""

    def __init__(self):
        super().__init__("ContentFetcher", "", "en")

    def fetch(self) -> List[Article]:
        return []
