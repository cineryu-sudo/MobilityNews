"""
디지털투데이 (DigitalToday) 모빌리티 섹션 크롤러.
FMS, 모빌리티 플랫폼, 카인포테인먼트 기사를 수집한다.
"""

from typing import List
from datetime import date
import re
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class DigitalTodayCrawler(BaseCrawler):
    """디지털투데이 모빌리티 섹션 크롤러."""

    def __init__(self):
        super().__init__(
            source_name="디지털투데이",
            base_url="https://www.digitaltoday.co.kr",
            language="ko"
        )

    def _parse_date(self, date_text: str):
        """날짜 문자열에서 date 객체 추출. 예: '2026.03.31' → date(2026, 3, 31)"""
        match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', date_text)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None
        return None

    def fetch(self) -> List[Article]:
        """디지털투데이 모빌리티 섹션에서 기사 수집."""
        # S1N13 = 모빌리티 섹션
        url = f"{self.base_url}/news/articleList.html?sc_section_code=S1N13"
        soup = self._get_soup(url)

        if not soup:
            return []

        articles = []
        seen_urls = set()

        # 기사 목록: <h4><a href="/news/articleView.html?idxno=...">제목</a></h4>
        headings = soup.select("h4 a[href*='articleView']")

        for link in headings:
            try:
                href = link.get("href", "")
                title = link.get_text(strip=True)

                if not href or not title or len(title) < 10:
                    continue

                # 절대 URL로 변환
                if href.startswith("/"):
                    href = f"{self.base_url}{href}"

                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # 날짜 추출: 기사 항목 근처의 날짜 텍스트를 탐색
                pub_date = None
                parent = link.find_parent("li") or link.find_parent("div")
                if parent:
                    date_el = parent.select_one(".byline em, .by-date, span.date")
                    if date_el:
                        pub_date = self._parse_date(date_el.get_text())

                articles.append(self._create_article(title, href, published_date=pub_date))

                if len(articles) >= MAX_ARTICLES_PER_SOURCE:
                    break

            except Exception as e:
                logger.warning(f"[디지털투데이] 기사 파싱 실패: {e}")
                continue

        logger.info(f"[디지털투데이] {len(articles)}개 기사 수집")
        return articles
