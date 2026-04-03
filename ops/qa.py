"""
Pre-send quality gate for the final briefing.
"""

from collections import Counter
import re
from typing import List

from config import DOMESTIC_COUNT, INTERNATIONAL_COUNT, QA_MIN_ARTICLE_COUNT
from ops.models import QaFinding, QaResult

SUMMARY_ERROR_MARKERS = {
    "요약을 생성할 수 없습니다.",
    "브리핑 생성 중 오류가 발생했습니다.",
}

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
        if article.url in seen_urls:
            findings.append(QaFinding("error", "duplicate_url", f"중복 URL 기사 발견: {article.url}"))
        seen_urls.add(article.url)

        normalized_title = _normalize_title(summary.original_title)
        if normalized_title in seen_titles:
            findings.append(QaFinding("error", "duplicate_title", f"중복 주제 기사 발견: {summary.original_title}"))
        seen_titles.add(normalized_title)

        summary_text = summary.summary.strip()
        if summary_text in SUMMARY_ERROR_MARKERS:
            findings.append(QaFinding("error", "summary_fallback", f"요약 생성 실패 기사: {summary.translated_title}"))
        elif len(summary_text) < 60:
            findings.append(QaFinding("warning", "summary_too_short", f"요약이 짧은 기사: {summary.translated_title}"))

        title_text = f"{summary.original_title} {summary.translated_title}".lower()
        if any(term in title_text for term in NON_MOBILITY_TERMS) and not any(
            term in title_text for term in MOBILITY_CONTEXT_TERMS
        ):
            findings.append(QaFinding("error", "off_topic_article", f"비모빌리티 기사 의심: {summary.translated_title}"))

        if summary.category == "기타":
            findings.append(QaFinding("warning", "uncategorized_article", f"카테고리가 '기타'인 기사: {summary.translated_title}"))

    if len(briefing.executive_insight.strip()) < 20:
        findings.append(QaFinding("warning", "weak_insight", "경영진 인사이트 문장이 지나치게 짧습니다."))

    blocked = any(finding.severity == "error" for finding in findings)
    return QaResult(passed=not blocked, blocked=blocked, findings=findings)
