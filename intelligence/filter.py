"""
Article filtering using two-step selection:
1) Rule-based priority ranking to reduce telecom-only noise.
2) LLM final pick with domestic/international quotas.
"""

import json
import logging
import re
from difflib import SequenceMatcher
from typing import List, Tuple

import anthropic

from crawlers.base import Article
from config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    DOMESTIC_COUNT,
    INTERNATIONAL_COUNT,
    COMPETITOR_KEYWORDS,
    MARKET_KEYWORDS,
)

logger = logging.getLogger(__name__)

# Priority buckets (high -> low)
# P1: 전체 모빌리티 시장/구조
# P2: 커넥티드카(통신+모빌리티)
# P3: 차량 인포테인먼트
# P4: FMS(Fleet Management System)
# 0: Out (telecom-only or weak mobility relevance)
PRIORITY_1_KEYWORDS = {
    "mobility market", "mobility industry", "maas", "robotaxi", "autonomous",
    "self-driving", "ev", "electric vehicle", "battery", "charging", "sdv",
    "v2x", "adas", "모빌리티 시장", "모빌리티 산업", "전기차", "자율주행",
    "배터리", "충전", "정책", "규제", "리콜",
}

PRIORITY_2_CONNECTED_CAR_TERMS = {
    "connected car", "connected vehicle", "telematics", "infotainment",
    "software-defined vehicle", "sdv", "ota", "5g", "lte", "v2x",
    "커넥티드카", "커넥티드 카", "텔레매틱스", "인포테인먼트", "소프트웨어 정의 차량",
}

PRIORITY_3_INFOTAINMENT_TERMS = {
    "infotainment", "in-car os", "carplay", "android auto", "head unit",
    "hmi", "cockpit", "digital cockpit", "ivis",
    "차량 인포테인먼트", "카플레이", "안드로이드 오토", "헤드유닛",
    "디지털 콕핏", "차량용 os", "차량용 앱",
}

PRIORITY_4_FMS_TERMS = {
    "fleet management", "fleet management system", "fms", "telematics platform",
    "fleet ops", "dispatch optimization", "route optimization",
    "차량관제", "관제 시스템", "플릿 관리", "플릿 매니지먼트", "운행 관제", "배차 최적화",
}

TELECOM_TERMS = {
    "telecom", "carrier", "5g", "lte", "통신", "이동통신", "유료방송", "가입자",
    "요금제", "망", "주파수", "통신사", "skt", "kt", "lg u+",
}

MOBILITY_SIGNAL_TERMS = {
    "mobility", "vehicle", "car", "automotive", "ev", "autonomous", "robotaxi",
    "모빌리티", "차량", "자동차", "전기차", "자율주행", "충전", "배터리",
    "완성차", "전장", "플릿", "로보택시", "모빌리티 플랫폼",
}


class ArticleFilter:
    """Filters and ranks articles using rule-based + LLM criteria."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def filter_top_articles(self, articles: List[Article]) -> List[Article]:
        """
        Split domestic/international and pick with quotas.
        - Domestic: DOMESTIC_COUNT
        - International: INTERNATIONAL_COUNT
        """
        if not articles:
            return []

        domestic = [a for a in articles if a.language == "ko"]
        international = [a for a in articles if a.language == "en"]

        logger.info(f"국내 후보 {len(domestic)}건, 해외 후보 {len(international)}건")

        selected_domestic = self._select_by_llm(domestic, DOMESTIC_COUNT, "국내")
        selected_international = self._select_by_llm(international, INTERNATIONAL_COUNT, "해외")

        # Safety-net A: if one side is empty, borrow 1~2 from the other side
        if len(selected_international) == 0 and domestic:
            borrow = min(2, len(domestic))
            supplement = self._select_fallback_generic(domestic, borrow, exclude=selected_domestic)
            selected_domestic.extend(supplement)
            logger.info(f"[보정] 해외 0건 -> 국내 대체 {len(supplement)}건")

        if len(selected_domestic) == 0 and international:
            borrow = min(2, len(international))
            supplement = self._select_fallback_generic(international, borrow, exclude=selected_international)
            selected_international.extend(supplement)
            logger.info(f"[보정] 국내 0건 -> 해외 대체 {len(supplement)}건")

        result = self._dedupe_preserve_order(selected_domestic + selected_international)
        result = self._remove_near_duplicates(result, label="최종")

        # Safety-net B: at least 2 articles from generic mobility signals
        if len(result) < 2:
            need = 2 - len(result)
            supplement = self._select_fallback_generic(articles, need, exclude=result)
            result.extend(supplement)
            result = self._dedupe_preserve_order(result)
            result = self._remove_near_duplicates(result, label="최종-보정")
            logger.info(f"[보정] 최소 기사수 보장 +{len(supplement)}건")

        logger.info(
            f"최종 선정: 국내 {len(selected_domestic)}건 + 해외 {len(selected_international)}건 = {len(result)}건"
        )
        return result

    def _dedupe_preserve_order(self, articles: List[Article]) -> List[Article]:
        seen = set()
        out = []
        for a in articles:
            if a.url in seen:
                continue
            seen.add(a.url)
            out.append(a)
        return out

    def _generic_mobility_score(self, article: Article) -> int:
        text = f"{article.title} {article.source}".lower()
        mob = sum(1 for kw in MOBILITY_SIGNAL_TERMS if kw in text)
        market = sum(1 for kw in MARKET_KEYWORDS[:15] if kw.lower() in text)
        competitor = sum(1 for kw in COMPETITOR_KEYWORDS[:15] if kw.lower() in text)
        tel = sum(1 for kw in TELECOM_TERMS if kw in text)
        # penalize telecom-only
        penalty = 2 if tel > 0 and mob == 0 else 0
        return max(0, mob + market + competitor - penalty)

    def _select_fallback_generic(
        self, articles: List[Article], count: int, exclude: List[Article] | None = None
    ) -> List[Article]:
        if count <= 0:
            return []
        exclude_urls = {a.url for a in (exclude or [])}
        scored = []
        for a in articles:
            if a.url in exclude_urls:
                continue
            score = self._generic_mobility_score(a)
            scored.append((score, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:count]]

    def _normalize_title(self, title: str) -> str:
        s = title.lower()
        s = re.sub(r"\[[^\]]+\]", " ", s)
        s = re.sub(r"\([^)]*\)", " ", s)
        s = re.sub(r"[^0-9a-z가-힣\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _title_similarity(self, title_a: str, title_b: str) -> Tuple[float, float]:
        a = self._normalize_title(title_a)
        b = self._normalize_title(title_b)
        if not a or not b:
            return 0.0, 0.0

        seq = SequenceMatcher(None, a, b).ratio()
        ta = set(t for t in a.split(" ") if len(t) >= 2)
        tb = set(t for t in b.split(" ") if len(t) >= 2)
        if not ta or not tb:
            jacc = 0.0
        else:
            jacc = len(ta & tb) / max(1, len(ta | tb))
        return seq, jacc

    def _remove_near_duplicates(self, articles: List[Article], label: str) -> List[Article]:
        """
        Remove near-duplicate stories (same topic, different publishers) in one daily letter.
        Keeps first article order.
        """
        kept: List[Article] = []
        removed = 0
        for article in articles:
            is_dup = False
            for prev in kept:
                seq, jacc = self._title_similarity(article.title, prev.title)
                if seq >= 0.90 or (seq >= 0.80 and jacc >= 0.55) or jacc >= 0.82:
                    is_dup = True
                    break
            if is_dup:
                removed += 1
            else:
                kept.append(article)

        if removed > 0:
            logger.info(f"[{label}] 유사 기사 {removed}건 제거")
        return kept

    def _classify_priority(self, article: Article) -> Tuple[int, int]:
        """
        Return (priority_bucket, score_hint).
        bucket:
          4 = P1 전체 모빌리티 시장/구조
          3 = P2 커넥티드카(통신+모빌리티)
          2 = P3 차량 인포테인먼트
          1 = P4 FMS
          0 = out (telecom-only)
        """
        text = f"{article.title} {article.source}".lower()

        p1 = sum(1 for kw in PRIORITY_1_KEYWORDS if kw in text)
        p2 = sum(1 for kw in PRIORITY_2_CONNECTED_CAR_TERMS if kw in text)
        p3 = sum(1 for kw in PRIORITY_3_INFOTAINMENT_TERMS if kw in text)
        p4 = sum(1 for kw in PRIORITY_4_FMS_TERMS if kw in text)
        tel = sum(1 for kw in TELECOM_TERMS if kw in text)
        mob = sum(1 for kw in MOBILITY_SIGNAL_TERMS if kw in text)

        if tel > 0 and mob == 0 and p1 == 0 and p2 == 0 and p3 == 0 and p4 == 0:
            return 0, 0

        if p1 > 0:
            return 4, p1 + mob

        if p2 > 0 and (tel > 0 or mob > 0):
            return 3, p2 + tel + mob

        # Explicit infotainment/FMS signals
        if p3 > 0:
            return 2, p3 + mob
        if p4 > 0:
            return 1, p4 + mob

        return 0, 0

    def _build_priority_pool(self, articles: List[Article], count: int, label: str) -> List[Article]:
        """Pre-rank by deterministic priority before LLM."""
        ranked = []
        for article in articles:
            bucket, hint = self._classify_priority(article)
            if bucket > 0:
                ranked.append((bucket, hint, article))

        if not ranked:
            logger.warning(f"[{label}] 규칙 기반 후보가 없어 제외합니다.")
            return []

        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        pool_size = min(len(ranked), max(count * 4, count))
        pool = [a for _, _, a in ranked[:pool_size]]

        c_p1 = sum(1 for b, _, _ in ranked[:pool_size] if b == 4)
        c_p2 = sum(1 for b, _, _ in ranked[:pool_size] if b == 3)
        c_p3 = sum(1 for b, _, _ in ranked[:pool_size] if b == 2)
        c_p4 = sum(1 for b, _, _ in ranked[:pool_size] if b == 1)
        pool = self._remove_near_duplicates(pool, label=f"{label}-사전")
        logger.info(f"[{label}] 사전 후보 {len(pool)}건 (P1:{c_p1}, P2:{c_p2}, P3:{c_p3}, P4:{c_p4})")

        return pool

    def _select_by_llm(self, articles: List[Article], count: int, label: str) -> List[Article]:
        """Use LLM to choose final articles from priority pool."""
        if not articles:
            return []

        priority_pool = self._build_priority_pool(articles, count, label)
        if not priority_pool:
            return []
        if len(priority_pool) <= count:
            return priority_pool[:count]

        article_list = "\n".join([
            f"{i+1}. [{a.source}] {a.title}"
            for i, a in enumerate(priority_pool)
        ])

        prompt = f"""당신은 모빌리티 산업 전문 에디터입니다.
아래 {label} 뉴스 목록에서 가장 중요한 {count}개를 선택해주세요.

우선순위(높음 -> 낮음):
1) 전체 모빌리티 시장/산업 구조 변화
2) 커넥티드카(통신 + 모빌리티 결합)
3) 차량 인포테인먼트
4) FMS(Fleet Management System) 관련

추가 기준:
- 통신 일반기사(모빌리티 맥락 약함)는 제외
- 경쟁사/시장 relevance를 함께 반영
- 경쟁사 관점 키워드: {', '.join(COMPETITOR_KEYWORDS[:10])}
- 시장 관점 키워드: {', '.join(MARKET_KEYWORDS[:10])}

기사 목록:
{article_list}

반드시 아래 JSON 형식만 출력하세요:
{{"selected_indices": [1, 2, 3]}}

selected_indices는 위 목록의 번호(1부터 시작)이며 정확히 {count}개여야 합니다."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)
            selected_indices = result.get("selected_indices", [])

            selected_articles = []
            for idx in selected_indices:
                real_idx = idx - 1
                if 0 <= real_idx < len(priority_pool):
                    selected_articles.append(priority_pool[real_idx])

            logger.info(f"[{label}] {len(articles)}건 중 {len(selected_articles)}건 선정")
            return selected_articles[:count] if selected_articles else priority_pool[:count]

        except Exception as e:
            logger.error(f"[{label}] LLM 필터링 실패: {e}")
            return priority_pool[:count]
