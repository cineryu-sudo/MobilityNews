"""
Article filtering using two-step selection:
1) Rule-based organization relevance ranking to reduce unrelated noise.
2) LLM final pick with domestic/international quotas and team balance.
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
    TOPIC_DEDUP_WEEKDAYS,
)
from intelligence.organization import (
    AI_INFO_TEAM,
    CONNECTED_CAR_TEAM,
    FMS_SOLUTION_TEAM,
    ORGANIZATION_TEAMS,
)

logger = logging.getLogger(__name__)

STRATEGIC_MOBILITY_TERMS = {
    "mobility market", "mobility industry", "maas", "robotaxi", "autonomous",
    "self-driving", "ev", "electric vehicle", "battery", "charging", "sdv",
    "v2x", "adas", "모빌리티 시장", "모빌리티 산업", "전기차", "자율주행",
    "배터리", "충전", "정책", "규제", "리콜", "로보택시", "모빌리티 플랫폼",
}

TEAM_RELEVANCE_TERMS = {
    CONNECTED_CAR_TEAM: {
        "connected car", "connected vehicle", "dcm", "tcu", "telematics",
        "software-defined vehicle", "sdv", "ota", "ecall", "v2x", "5g vehicle",
        "커넥티드카", "커넥티드 카", "텔레매틱스", "차량 통신", "차량용 통신",
        "소프트웨어 정의 차량", "차량 데이터", "차량용 esim",
    },
    AI_INFO_TEAM: {
        "infotainment", "in-car os", "carplay", "android auto", "head unit",
        "hmi", "cockpit", "digital cockpit", "ivis", "in-vehicle ai",
        "automotive ai assistant", "voice assistant", "vehicle app store",
        "apple maps", "google maps", "navigation",
        "차량 인포테인먼트", "카플레이", "안드로이드 오토", "헤드유닛",
        "디지털 콕핏", "차량용 os", "차량용 앱", "차량용 ai", "음성비서",
        "애플 지도", "구글 지도", "내비게이션",
    },
    FMS_SOLUTION_TEAM: {
        "fleet management", "fleet management system", "fms", "telematics platform",
        "fleet ops", "dispatch optimization", "route optimization", "vehicle tracking",
        "precise positioning", "high-precision positioning", "rtk", "gnss",
        "commercial fleet", "last-mile logistics", "predictive maintenance",
        "robotaxi", "autonomous fleet",
        "차량관제", "관제 시스템", "플릿 관리", "플릿 매니지먼트", "운행 관제",
        "배차 최적화", "초정밀측위", "정밀측위", "차량 추적", "물류 차량",
        "예지정비", "로보택시",
    },
}

TELECOM_TERMS = {
    "telecom", "carrier", "5g", "lte", "통신", "이동통신", "유료방송", "가입자",
    "요금제", "망", "주파수", "통신사", "skt", "kt", "lg u+",
}

MOBILITY_SIGNAL_TERMS = {
    "mobility", "vehicle", "car", "automotive", "ev", "autonomous", "robotaxi",
    "모빌리티", "차량", "자동차", "전기차", "자율주행", "충전", "배터리",
    "완성차", "전장", "플릿", "로보택시", "모빌리티 플랫폼", "택시", "자율차",
    "물류", "측위", "인포테인먼트", "커넥티드카",
}

NON_MOBILITY_EXCLUSION_TERMS = {
    "스마트폰", "휴대폰", "게임", "아이폰", "갤럭시", "포코",
    "콘진원", "klpga", "sports", "리듬하이브", "라인게임즈", "넥슨",
}


def _contains_term(text: str, term: str) -> bool:
    """Match ASCII keywords on word boundaries and Korean keywords by substring."""
    normalized_term = term.lower()
    if normalized_term.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return normalized_term in text


def _parse_json_object(text: str) -> dict:
    """Extract the first valid JSON object from prose or a fenced response."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("LLM 응답에서 JSON 객체를 찾을 수 없습니다.")


def score_team_relevance(article: Article) -> dict[str, int]:
    """Return deterministic relevance scores for each business team."""
    text = f"{article.title} {article.source}".lower()
    return {
        team: sum(1 for term in terms if _contains_term(text, term))
        for team, terms in TEAM_RELEVANCE_TERMS.items()
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

        initially_selected = selected_domestic + selected_international
        result = self._dedupe_preserve_order(initially_selected)
        result = self._remove_near_duplicates(result, label="최종")
        result = self._remove_semantic_duplicates(result)
        result = self._supplement_language_quotas(
            result,
            articles,
            exclude=initially_selected,
        )

        target_count = min(DOMESTIC_COUNT + INTERNATIONAL_COUNT, len(articles))
        if len(result) < target_count:
            need = target_count - len(result)
            supplement = self._select_fallback_generic(
                articles,
                need,
                exclude=initially_selected + result,
            )
            result.extend(supplement)
            result = self._dedupe_preserve_order(result)
            result = self._remove_near_duplicates(result, label="최종-보정")
            logger.info(f"[보정] 목표 기사수 보장 +{len(supplement)}건")

        final_domestic = sum(article.language == "ko" for article in result)
        final_international = sum(article.language == "en" for article in result)
        logger.info(f"최종 선정: 국내 {final_domestic}건 + 해외 {final_international}건 = {len(result)}건")
        return result

    def _supplement_language_quotas(
        self,
        selected: List[Article],
        candidates: List[Article],
        exclude: List[Article] | None = None,
    ) -> List[Article]:
        """Refill language quotas after duplicate removal without reusing rejected stories."""
        result = list(selected)
        excluded = list(exclude or []) + result
        targets = {"ko": DOMESTIC_COUNT, "en": INTERNATIONAL_COUNT}

        for language, target in targets.items():
            current = sum(article.language == language for article in result)
            need = max(0, target - current)
            if need == 0:
                continue

            language_candidates = [
                article for article in candidates if article.language == language
            ]
            supplement = self._select_fallback_generic(
                language_candidates,
                need,
                exclude=excluded,
            )
            if supplement:
                result.extend(supplement)
                excluded.extend(supplement)
                logger.info(f"[보정] {language} 기사 할당 복원 +{len(supplement)}건")

        return result

    def _remove_semantic_duplicates(self, articles: List[Article]) -> List[Article]:
        """Remove cross-language reports about the exact same event or announcement."""
        if len(articles) < 2:
            return articles

        article_list = "\n".join(
            f"{index + 1}. [{article.source}] {article.title}"
            for index, article in enumerate(articles)
        )
        prompt = f"""아래 모빌리티 기사 중 동일한 사건, 발표, 제품 공개를 다룬 중복 보도를 찾으세요.
언어가 달라도 같은 사건이면 중복입니다. 같은 기업이나 넓은 주제만 같고 사건이 다르면 중복이 아닙니다.
중복 묶음에서는 목록에서 뒤에 있는 기사 번호만 제거 대상으로 선택하세요.

기사 목록:
{article_list}

반드시 아래 JSON 형식만 출력하세요:
{{"duplicate_indices": [4]}}

중복이 없으면 {{"duplicate_indices": []}}로 출력하세요."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _parse_json_object(response.content[0].text)
            duplicate_indices = {
                index - 1
                for index in result.get("duplicate_indices", [])
                if isinstance(index, int) and 1 <= index <= len(articles)
            }
            if duplicate_indices:
                logger.info(f"[최종] 의미 중복 기사 {len(duplicate_indices)}건 제거")
            return [
                article
                for index, article in enumerate(articles)
                if index not in duplicate_indices
            ]
        except Exception as error:
            logger.warning(f"[최종] 의미 중복 검사 실패, 기존 선정을 유지합니다: {error}")
            return articles

    def _dedupe_preserve_order(self, articles: List[Article]) -> List[Article]:
        seen = set()
        out = []
        for article in articles:
            if article.url in seen:
                continue
            seen.add(article.url)
            out.append(article)
        return out

    def _generic_mobility_score(self, article: Article) -> int:
        text = f"{article.title} {article.source}".lower()
        mobility = sum(1 for kw in MOBILITY_SIGNAL_TERMS if _contains_term(text, kw))
        market = sum(1 for kw in MARKET_KEYWORDS[:15] if _contains_term(text, kw))
        competitor = sum(1 for kw in COMPETITOR_KEYWORDS[:15] if _contains_term(text, kw))
        telecom = sum(1 for kw in TELECOM_TERMS if _contains_term(text, kw))
        team_scores = score_team_relevance(article)
        team_hits = sum(min(score, 2) for score in team_scores.values())
        cross_team_bonus = 2 if sum(score > 0 for score in team_scores.values()) >= 2 else 0
        penalty = 2 if telecom > 0 and mobility == 0 else 0
        return max(0, mobility + market + competitor + team_hits + cross_team_bonus - penalty)

    def _select_fallback_generic(
        self, articles: List[Article], count: int, exclude: List[Article] | None = None
    ) -> List[Article]:
        if count <= 0:
            return []

        exclude_urls = {article.url for article in (exclude or [])}
        remaining = [article for article in articles if article.url not in exclude_urls]
        covered_teams = set()
        for article in exclude or []:
            covered_teams.update(
                team for team, score in score_team_relevance(article).items() if score > 0
            )

        selected = []
        while remaining and len(selected) < count:
            best = max(
                remaining,
                key=lambda article: (
                    len(
                        {
                            team
                            for team, score in score_team_relevance(article).items()
                            if score > 0
                        }
                        - covered_teams
                    ),
                    self._generic_mobility_score(article),
                ),
            )
            selected.append(best)
            covered_teams.update(
                team for team, score in score_team_relevance(best).items() if score > 0
            )
            remaining.remove(best)
        return selected

    def _normalize_title(self, title: str) -> str:
        normalized = title.lower()
        normalized = re.sub(r"\[[^\]]+\]", " ", normalized)
        normalized = re.sub(r"\([^)]*\)", " ", normalized)
        normalized = re.sub(r"[^0-9a-z가-힣\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _title_similarity(self, title_a: str, title_b: str) -> Tuple[float, float]:
        normalized_a = self._normalize_title(title_a)
        normalized_b = self._normalize_title(title_b)
        if not normalized_a or not normalized_b:
            return 0.0, 0.0

        sequence_ratio = SequenceMatcher(None, normalized_a, normalized_b).ratio()
        tokens_a = {token for token in normalized_a.split(" ") if len(token) >= 2}
        tokens_b = {token for token in normalized_b.split(" ") if len(token) >= 2}
        if not tokens_a or not tokens_b:
            jaccard = 0.0
        else:
            jaccard = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
        return sequence_ratio, jaccard

    def _remove_near_duplicates(self, articles: List[Article], label: str) -> List[Article]:
        """Remove near-duplicate stories while preserving article order."""
        kept: List[Article] = []
        removed = 0

        for article in articles:
            is_duplicate = False
            for previous in kept:
                sequence_ratio, jaccard = self._title_similarity(article.title, previous.title)
                if (
                    sequence_ratio >= 0.90
                    or (sequence_ratio >= 0.80 and jaccard >= 0.55)
                    or jaccard >= 0.82
                ):
                    is_duplicate = True
                    break

            if is_duplicate:
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
          4 = multiple business teams
          3 = one business team
          2 = strategic mobility signal
          1 = generic mobility signal
          0 = out (telecom-only)
        """
        text = f"{article.title} {article.source}".lower()

        strategic = sum(1 for kw in STRATEGIC_MOBILITY_TERMS if _contains_term(text, kw))
        team_scores = score_team_relevance(article)
        relevant_team_count = sum(score > 0 for score in team_scores.values())
        team_score = sum(team_scores.values())
        telecom = sum(1 for kw in TELECOM_TERMS if _contains_term(text, kw))
        mobility = sum(1 for kw in MOBILITY_SIGNAL_TERMS if _contains_term(text, kw))
        competitor = sum(1 for kw in COMPETITOR_KEYWORDS if _contains_term(text, kw))
        market = sum(1 for kw in MARKET_KEYWORDS if _contains_term(text, kw))

        if any(_contains_term(text, term) for term in NON_MOBILITY_EXCLUSION_TERMS) and mobility == 0:
            return 0, 0

        if telecom > 0 and mobility == 0 and team_score == 0 and strategic == 0:
            return 0, 0

        score_hint = team_score + strategic + mobility + competitor + market
        if relevant_team_count >= 2:
            return 4, score_hint
        if relevant_team_count == 1:
            return 3, score_hint
        if strategic > 0:
            return 2, score_hint
        if mobility > 0:
            return 1, score_hint
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

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        pool_size = min(len(ranked), max(count * 4, count))
        pool = self._select_fallback_generic(
            [article for _, _, article in ranked],
            pool_size,
        )

        team_counts = {
            team: sum(score_team_relevance(article)[team] > 0 for article in pool)
            for team in ORGANIZATION_TEAMS
        }
        cross_team_count = sum(
            sum(score > 0 for score in score_team_relevance(article).values()) >= 2
            for article in pool
        )
        pool = self._remove_near_duplicates(pool, label=f"{label}-사전")
        coverage_log = ", ".join(f"{team}:{count}" for team, count in team_counts.items())
        logger.info(
            f"[{label}] 사전 후보 {len(pool)}건 ({coverage_log}, 교차조직:{cross_team_count})"
        )
        return pool

    def _select_by_llm(self, articles: List[Article], count: int, label: str) -> List[Article]:
        """Use LLM to choose final articles from the pre-ranked priority pool."""
        if not articles:
            return []

        priority_pool = self._build_priority_pool(articles, count, label)
        if not priority_pool:
            return []
        if len(priority_pool) <= count:
            return priority_pool[:count]

        article_lines = []
        for index, article in enumerate(priority_pool):
            team_scores = score_team_relevance(article)
            related_teams = [team for team, score in team_scores.items() if score > 0]
            team_hint = ", ".join(related_teams) or "공통 모빌리티"
            article_lines.append(
                f"{index + 1}. [{article.source}] {article.title} "
                f"(예상 관련 조직: {team_hint})"
            )
        article_list = "\n".join(article_lines)

        prompt = f"""당신은 LG유플러스 모빌리티 산업 전문 에디터입니다.
아래 {label} 뉴스 목록에서 가장 중요한 {count}개를 선택해주세요.

조직 관점:
- 커넥티드카사업팀: 통신 사업, DCM 개발, DCM 운영
- AI인포사업팀: 차량 인포테인먼트 및 AI 기반 차량 경험
- FMS솔루션사업팀: 초정밀측위, 차량 관제 및 운영 솔루션

선정 원칙:
- 세 조직 사이에 우선순위를 두지 말고 관련 기사가 한 조직에 편중되지 않도록 구성
- 여러 조직에 동시에 영향을 주는 교차 조직 신호를 우선 검토
- 시장 구조 변화, 사업 영향, 시의성, 근거의 구체성을 함께 평가

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

            result = _parse_json_object(response.content[0].text)
            selected_indices = result.get("selected_indices", [])

            selected_articles = []
            seen_indices = set()
            for idx in selected_indices:
                real_idx = idx - 1
                if 0 <= real_idx < len(priority_pool) and real_idx not in seen_indices:
                    selected_articles.append(priority_pool[real_idx])
                    seen_indices.add(real_idx)

            logger.info(f"[{label}] {len(articles)}건 중 {len(selected_articles)}건 선정")
            if len(selected_articles) < count:
                selected_articles.extend(
                    self._select_fallback_generic(
                        priority_pool,
                        count - len(selected_articles),
                        exclude=selected_articles,
                    )
                )
            return selected_articles[:count]

        except Exception as error:
            logger.error(f"[{label}] LLM 필터링 실패: {error}")
            return self._select_fallback_generic(priority_pool, count)

    def remove_duplicate_topics(self, articles: List[Article], recent_titles: List[str]) -> List[Article]:
        """
        최근 TOPIC_DEDUP_WEEKDAYS 내 발송된 기사와 같은 주제/내용의 기사를 제거한다.
        """
        if not recent_titles or not articles:
            return articles

        article_list = "\n".join(
            f"{index + 1}. {article.title}"
            for index, article in enumerate(articles)
        )
        recent_list = "\n".join(f"- {title}" for title in recent_titles)

        prompt = f"""당신은 뉴스레터 에디터입니다.
아래 '최근 발송된 기사'와 동일하거나 매우 유사한 주제를 다루는 '신규 후보 기사' 번호를 찾아주세요.

중복으로 판단하는 기준:
- 같은 사건/사고를 다루는 경우
- 같은 회사의 같은 발표/제품/정책을 다루는 경우
- 단순 업데이트(후속 보도)인 경우

최근 발송된 기사 (평일 {TOPIC_DEDUP_WEEKDAYS}일 이내):
{recent_list}

신규 후보 기사:
{article_list}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"duplicate_indices": [1, 3]}}

중복이 없으면: {{"duplicate_indices": []}}

duplicate_indices는 신규 후보 기사 목록에서 최근 발송 기사와 주제가 중복되는 기사 번호입니다 (1부터 시작)."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            result = _parse_json_object(response.content[0].text)
            duplicate_indices = set(result.get("duplicate_indices", []))
            filtered = [
                article for index, article in enumerate(articles, 1)
                if index not in duplicate_indices
            ]

            removed = len(articles) - len(filtered)
            if removed > 0:
                logger.info(f"주제 중복 기사 {removed}건 제거 (최근 {TOPIC_DEDUP_WEEKDAYS} 영업일 이내 발송 기사와 중복)")

            return filtered

        except Exception as error:
            logger.error(f"주제 중복 제거 실패: {error}")
            return articles
