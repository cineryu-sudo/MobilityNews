"""
Source health checks for crawler runs.
"""

from collections import defaultdict
from typing import Dict, Iterable, List

from config import (
    WATCHDOG_ALERT_STREAK,
    WATCHDOG_LOW_YIELD_THRESHOLD,
    WATCHDOG_MIN_TOTAL_ARTICLES,
)
from ops.models import SourceRunResult


def _source_history_map(recent_reports: Iterable[dict]) -> Dict[str, List[dict]]:
    history: Dict[str, List[dict]] = defaultdict(list)
    for report in recent_reports:
        for result in report.get("source_results", []):
            source_name = result.get("source_name")
            if source_name:
                history[source_name].append(result)
    return history


def _problem_streak(results: List[dict]) -> int:
    streak = 0
    for result in reversed(results):
        success = result.get("success", False)
        article_count = result.get("article_count", 0)
        if success and article_count > 0:
            break
        streak += 1
    return streak


def evaluate_source_results(
    source_results: List[SourceRunResult],
    recent_reports: List[dict],
) -> tuple[List[SourceRunResult], List[str]]:
    """Annotate source results and return run-level watchdog alerts."""
    alerts: List[str] = []
    history_map = _source_history_map(recent_reports)

    total_articles = sum(result.article_count for result in source_results)
    if total_articles < WATCHDOG_MIN_TOTAL_ARTICLES:
        alerts.append(
            f"총 수집 기사 수가 {total_articles}건으로 낮습니다 "
            f"(권장 최소 {WATCHDOG_MIN_TOTAL_ARTICLES}건)."
        )

    for result in source_results:
        if not result.success:
            result.warnings.append("fetch_failed")
        elif result.article_count == 0:
            result.warnings.append("no_articles_collected")
        elif result.article_count <= WATCHDOG_LOW_YIELD_THRESHOLD:
            result.warnings.append("low_yield")

        current_problem = (not result.success) or result.article_count == 0
        streak = _problem_streak(history_map.get(result.source_name, []))
        if current_problem and streak + 1 >= WATCHDOG_ALERT_STREAK:
            alerts.append(
                f"{result.source_name}: 문제 실행이 {streak + 1}회 연속 발생했습니다."
            )

    return source_results, alerts
