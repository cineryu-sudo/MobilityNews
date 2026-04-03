"""
Heuristic source-scout suggestions and coverage-gap analysis.
"""

from collections import Counter
from typing import Iterable, List

from ops.models import ScoutSuggestion, SourceRunResult

COVERAGE_GAPS = {
    "정책/규제": "정책·규제 소스 비중이 낮습니다. 정부/산업 정책 전문 소스를 보강하세요.",
    "충전인프라": "충전 인프라 기사 비중이 낮습니다. 충전 사업자·인프라 전문 소스를 검토하세요.",
    "커넥티드카": "커넥티드카/텔레매틱스 소스 비중이 낮습니다. 차량 소프트웨어 소스를 보강하세요.",
    "MaaS": "플랫폼·MaaS 기사 비중이 낮습니다. 호출·플랫폼·교통 서비스 소스를 보강하세요.",
}


def build_source_scout_suggestions(
    source_results: List[SourceRunResult],
    recent_reports: Iterable[dict],
    current_selected_articles: List[dict],
) -> List[ScoutSuggestion]:
    """Generate scout suggestions from source health and recent category coverage."""
    suggestions: List[ScoutSuggestion] = []

    for result in source_results:
        if not result.success:
            suggestions.append(
                ScoutSuggestion(
                    kind="source_health",
                    source_name=result.source_name,
                    reason="이번 실행에서 fetch 실패가 발생했습니다.",
                    suggestion="선택자 변경 여부를 점검하고, 가능하면 RSS 기반 대체 수집 경로를 검토하세요.",
                )
            )
        elif result.article_count == 0:
            suggestions.append(
                ScoutSuggestion(
                    kind="source_health",
                    source_name=result.source_name,
                    reason="이번 실행에서 수집 기사 수가 0건입니다.",
                    suggestion="소스 구조를 점검하거나 동일 카테고리의 대체 소스를 발굴하세요.",
                )
            )

    category_counts = Counter()
    for report in recent_reports:
        for article in report.get("selected_articles", []):
            category = article.get("category")
            if category:
                category_counts[category] += 1
    for article in current_selected_articles:
        category = article.get("category")
        if category:
            category_counts[category] += 1

    for category, suggestion in COVERAGE_GAPS.items():
        if category_counts.get(category, 0) == 0:
            suggestions.append(
                ScoutSuggestion(
                    kind="coverage_gap",
                    source_name=category,
                    reason="최근 7일 운영 리포트에서 해당 카테고리 커버리지가 확인되지 않았습니다.",
                    suggestion=suggestion,
                )
            )

    deduped: List[ScoutSuggestion] = []
    seen = set()
    for suggestion in suggestions:
        key = (suggestion.kind, suggestion.source_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
    return deduped[:8]
