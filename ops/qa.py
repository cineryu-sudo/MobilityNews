"""
Pre-send quality gate for the final briefing.
"""

from collections import Counter
import re
from typing import List
from urllib.parse import urlparse

from config import DOMESTIC_COUNT, INTERNATIONAL_COUNT, QA_MIN_ARTICLE_COUNT
from intelligence.organization import ALL_TEAM_TAGS, ORGANIZATION_TEAMS
from ops.models import QaFinding, QaResult

SUMMARY_ERROR_MARKERS = {
    "요약을 생성할 수 없습니다.",
    "브리핑 생성 중 오류가 발생했습니다.",
}

# substring 매칭용 fallback 패턴. summarize.py의 fallback 문구가 변형되어도
# ("기사 요약을 생성할 수 없습니다." 등) 누락 없이 차단하기 위함이다.
FALLBACK_TEXT_PATTERNS = (
    "생성할 수 없습니다",
    "오류가 발생했습니다",
    "분석 중입니다",
)


def _contains_fallback_text(text: str) -> bool:
    """Return True if text contains any known fallback marker."""
    stripped = text.strip()
    if stripped in SUMMARY_ERROR_MARKERS:
        return True
    return any(pattern in stripped for pattern in FALLBACK_TEXT_PATTERNS)

NON_MOBILITY_TERMS = {
    "스마트폰", "휴대폰", "아이폰", "갤럭시", "포코", "게임",
    "klpga", "스포츠", "리듬하이브", "라인게임즈", "넥슨",
}

MOBILITY_CONTEXT_TERMS = {
    "모빌리티", "로보택시", "택시", "자율주행", "자율차", "차량", "자동차",
    "우버", "카카오모빌리티", "vehicle", "car", "automotive", "robotaxi",
    "autonomous", "fleet", "telematics", "charging", "ev",
}


def _normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"\[[^\]]+\]", " ", normalized)
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = re.sub(r"[^0-9a-z가-힣\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def evaluate_briefing(selected_articles, briefing) -> QaResult:
    """Validate the final briefing before delivery."""
    findings: List[QaFinding] = []
    covered_teams = set()
    cross_team_signals = 0

    if len(selected_articles) != len(briefing.articles):
        findings.append(QaFinding("error", "article_mismatch", "선정 기사와 브리핑 기사 수가 일치하지 않습니다."))

    if len(briefing.articles) < QA_MIN_ARTICLE_COUNT:
        findings.append(
            QaFinding(
                "error",
                "insufficient_articles",
                f"최종 브리핑 기사 수가 {len(briefing.articles)}건입니다. 최소 {QA_MIN_ARTICLE_COUNT}건이 필요합니다.",
            )
        )

    language_counts = Counter(article.language for article in selected_articles)
    if language_counts.get("ko", 0) < DOMESTIC_COUNT:
        findings.append(
            QaFinding(
                "warning",
                "domestic_quota_short",
                f"국내 기사 수가 {language_counts.get('ko', 0)}건으로 목표 {DOMESTIC_COUNT}건보다 적습니다.",
            )
        )
    if language_counts.get("en", 0) < INTERNATIONAL_COUNT:
        findings.append(
            QaFinding(
                "warning",
                "international_quota_short",
                f"해외 기사 수가 {language_counts.get('en', 0)}건으로 목표 {INTERNATIONAL_COUNT}건보다 적습니다.",
            )
        )

    seen_urls = set()
    seen_titles = set()
    for article, summary in zip(selected_articles, briefing.articles):
        parsed_url = urlparse(article.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            findings.append(QaFinding("error", "invalid_url", f"유효하지 않은 기사 URL: {article.url}"))

        if article.url in seen_urls:
            findings.append(QaFinding("error", "duplicate_url", f"중복 URL 기사 발견: {article.url}"))
        seen_urls.add(article.url)

        normalized_title = _normalize_title(summary.original_title)
        if normalized_title in seen_titles:
            findings.append(QaFinding("error", "duplicate_title", f"중복 주제 기사 발견: {summary.original_title}"))
        seen_titles.add(normalized_title)

        summary_text = summary.summary.strip()
        if _contains_fallback_text(summary_text):
            findings.append(QaFinding("error", "summary_fallback", f"요약 생성 실패 기사: {summary.translated_title}"))
        elif len(summary_text) < 60:
            findings.append(QaFinding("warning", "summary_too_short", f"요약이 짧은 기사: {summary.translated_title}"))

        if len(summary.key_points) != 3:
            findings.append(
                QaFinding(
                    "error",
                    "invalid_key_point_count",
                    f"핵심 포인트가 3개가 아닌 기사: {summary.translated_title}",
                )
            )
        else:
            normalized_points = {
                re.sub(r"\s+", " ", point.strip().lower())
                for point in summary.key_points
                if point.strip()
            }
            if len(normalized_points) != 3:
                findings.append(
                    QaFinding(
                        "error",
                        "duplicate_key_points",
                        f"핵심 포인트가 비어 있거나 중복된 기사: {summary.translated_title}",
                    )
                )
            for point in summary.key_points:
                if _contains_fallback_text(point):
                    findings.append(
                        QaFinding(
                            "error",
                            "key_point_fallback",
                            f"핵심 포인트 생성 실패 기사: {summary.translated_title}",
                        )
                    )
                    break

        why_it_matters = summary.why_it_matters.strip()
        if not why_it_matters or _contains_fallback_text(why_it_matters):
            findings.append(
                QaFinding(
                    "error",
                    "missing_why_it_matters",
                    f"산업 중요성 설명이 없는 기사: {summary.translated_title}",
                )
            )
        elif len(why_it_matters) < 20:
            findings.append(
                QaFinding(
                    "warning",
                    "weak_why_it_matters",
                    f"산업 중요성 설명이 짧은 기사: {summary.translated_title}",
                )
            )

        if not summary.related_teams:
            findings.append(
                QaFinding(
                    "error",
                    "missing_related_teams",
                    f"관련 조직 태그가 없는 기사: {summary.translated_title}",
                )
            )
        else:
            invalid_teams = set(summary.related_teams) - set(ALL_TEAM_TAGS)
            if invalid_teams:
                findings.append(
                    QaFinding(
                        "error",
                        "invalid_related_team",
                        f"잘못된 조직 태그 {sorted(invalid_teams)}: {summary.translated_title}",
                    )
                )
            article_teams = set(summary.related_teams) & set(ORGANIZATION_TEAMS)
            covered_teams.update(article_teams)
            if len(article_teams) >= 2:
                cross_team_signals += 1

        if not summary.watch_point.strip():
            findings.append(
                QaFinding(
                    "warning",
                    "missing_watch_point",
                    f"후속 관찰 포인트가 없는 기사: {summary.translated_title}",
                )
            )

        title_text = f"{summary.original_title} {summary.translated_title}".lower()
        if any(term in title_text for term in NON_MOBILITY_TERMS) and not any(
            term in title_text for term in MOBILITY_CONTEXT_TERMS
        ):
            findings.append(QaFinding("error", "off_topic_article", f"비모빌리티 기사 의심: {summary.translated_title}"))

        if summary.category == "기타":
            findings.append(QaFinding("warning", "uncategorized_article", f"카테고리가 '기타'인 기사: {summary.translated_title}"))

    for team in ORGANIZATION_TEAMS:
        if team not in covered_teams:
            findings.append(
                QaFinding(
                    "warning",
                    "organization_coverage_gap",
                    f"이번 브리핑에 {team} 직접 관련 기사가 없습니다.",
                )
            )

    if briefing.articles and cross_team_signals == 0:
        findings.append(
            QaFinding(
                "warning",
                "cross_team_signal_missing",
                "여러 사업팀에 동시에 관련된 교차 조직 신호가 없습니다.",
            )
        )

    insight_text = briefing.executive_insight.strip()
    if _contains_fallback_text(insight_text):
        findings.append(
            QaFinding(
                "error",
                "insight_fallback",
                "경영진 인사이트가 fallback 문구로 채워졌습니다. LLM 호출 실패 가능성이 있어 발송을 차단합니다.",
            )
        )
    elif len(insight_text) < 20:
        findings.append(QaFinding("warning", "weak_insight", "경영진 인사이트 문장이 지나치게 짧습니다."))

    blocked = any(finding.severity == "error" for finding in findings)
    return QaResult(passed=not blocked, blocked=blocked, findings=findings)
