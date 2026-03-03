"""
Article filtering using LLM to select articles by domestic/international ratio.
- 국내(ko) 기사 3건 + 해외(en) 기사 2건 = 총 5건
- 경쟁사 뉴스(70%) + 시장 지표(30%) 기준으로 우선순위 결정
"""

import json
import logging
from typing import List

import anthropic

from crawlers.base import Article
from config import (
    ANTHROPIC_API_KEY, LLM_MODEL,
    DOMESTIC_COUNT, INTERNATIONAL_COUNT,
    COMPETITOR_KEYWORDS, MARKET_KEYWORDS,
)

logger = logging.getLogger(__name__)


class ArticleFilter:
    """Filters and ranks articles using LLM based on relevance criteria."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def filter_top_articles(self, articles: List[Article]) -> List[Article]:
        """
        국내/해외 기사를 분리한 뒤 각각 LLM으로 필터링.
        - 국내(ko) → DOMESTIC_COUNT(3)건 선정
        - 해외(en) → INTERNATIONAL_COUNT(2)건 선정
        """
        if not articles:
            return []

        # 국내/해외 기사 분리 (language 필드 기준)
        domestic = [a for a in articles if a.language == "ko"]
        international = [a for a in articles if a.language == "en"]

        logger.info(f"국내 후보 {len(domestic)}건, 해외 후보 {len(international)}건")

        # 각각 LLM 필터링
        selected_domestic = self._select_by_llm(domestic, DOMESTIC_COUNT, "국내")
        selected_international = self._select_by_llm(international, INTERNATIONAL_COUNT, "해외")

        # 국내 기사 먼저, 해외 기사 뒤에 배치
        result = selected_domestic + selected_international
        logger.info(f"최종 선정: 국내 {len(selected_domestic)}건 + 해외 {len(selected_international)}건 = {len(result)}건")
        return result

    def _select_by_llm(self, articles: List[Article], count: int, label: str) -> List[Article]:
        """LLM을 사용하여 주어진 기사 목록에서 count개 선정."""
        # 후보가 요청 수 이하면 그대로 반환
        if len(articles) <= count:
            return articles

        # LLM에 보낼 기사 목록 준비
        article_list = "\n".join([
            f"{i+1}. [{a.source}] {a.title}"
            for i, a in enumerate(articles)
        ])

        prompt = f"""당신은 모빌리티 업계 전문 에디터입니다.
아래 {label} 뉴스 기사 목록에서 가장 중요한 {count}개를 선정해주세요.

선정 기준:
1. 경쟁사 관련 뉴스 (70% 비중): {', '.join(COMPETITOR_KEYWORDS[:10])} 등
2. 시장 지표/트렌드 (30% 비중): {', '.join(MARKET_KEYWORDS[:10])} 등

기사 목록:
{article_list}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"selected_indices": [1, 2, 3]}}

selected_indices는 위 목록에서 선정한 기사의 번호입니다 (1부터 시작, 정확히 {count}개)."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # 마크다운 코드블록 처리
            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)
            selected_indices = result.get("selected_indices", [])

            # 1-indexed → 0-indexed 변환
            selected_articles = []
            for idx in selected_indices:
                real_idx = idx - 1
                if 0 <= real_idx < len(articles):
                    selected_articles.append(articles[real_idx])

            logger.info(f"[{label}] {len(articles)}건 중 {len(selected_articles)}건 선정")
            return selected_articles[:count]

        except Exception as e:
            logger.error(f"[{label}] LLM 필터링 실패: {e}")
            # 실패 시 앞에서부터 count개 반환
            return articles[:count]
