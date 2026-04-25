"""
오토헤럴드 (AutoHerald) 하이AI/모빌리티 섹션 크롤러.
자율주행, SDV, 커넥티드카, 모빌리티 산업 뉴스를 수집한다.
"""

from typing import List
from datetime import date
import re
import logging

from .base import BaseCrawler, Article
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class AutoHeraldCrawler(BaseCrawler):
    """오토헤럴드 하이AI/모빌리티 섹션 크롤러."""

    def __init__(self):
        super().__init__(
            source_name="오토헤럴드",
            base_url="https://www.autoherald.co.kr",
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
        """오토헤럴드 하이AI 섹션에서 기사 수집."""
        # S1N14 = 하이AI (자율주행/SDV/모빌리티) 섹션
        url = f"{self.base_url}/news/articleList.html?sc_section_code=S1N14"
        soup = self._get_soup(url)

        if not soup:
            return []

        articles = []
        seen_urls = set()

        # 기사 목록: <a href="/news/articleView.html?idxno=...">제목</a>
        # titles 클래스 내부의 링크 또는 h4 내부의 링크를 대상으로 함
        links = soup.select(".titles a[href*='articleView'], h4 a[href*='articleView']")

        for link in links:
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
                logger.warning(f"[오토헤럴드] 기사 파싱 실패: {e}")
                continue

        logger.info(f"[오토헤럴드] {len(articles)}개 기사 수집")
        return articles
