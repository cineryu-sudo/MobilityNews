"""
Run report persistence and markdown summaries.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Iterable, List

from config import RUN_ARTIFACTS_DIR, WEEKLY_REPORTS_DIR
from ops.models import RunReport, ScoutSuggestion, to_serializable


def build_run_id(now: datetime | None = None) -> str:
    """Build a stable timestamp-based run id."""
    now = now or datetime.now()
    return now.strftime("%Y%m%dT%H%M%S")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_run_dir(run_id: str) -> Path:
    """Return the artifact directory for one run."""
    return _ensure_dir(Path(RUN_ARTIFACTS_DIR) / run_id)


def write_preview_html(run_id: str, html_content: str) -> str:
    """Write preview HTML into the run artifact folder and project root preview."""
    run_dir = get_run_dir(run_id)
    preview_path = run_dir / "preview_email.html"
    preview_path.write_text(html_content, encoding="utf-8")
    Path("preview_email.html").write_text(html_content, encoding="utf-8")
    return str(preview_path)


def save_approval_draft(run_id: str, draft: dict) -> str:
    """Persist a manual-approval draft."""
    run_dir = get_run_dir(run_id)
    draft_path = run_dir / "approval_draft.json"
    draft_path.write_text(
        json.dumps(to_serializable(draft), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(draft_path)


def load_approval_draft(path: str) -> dict:
    """Load a previously saved approval draft."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_recent_run_reports(days: int = 7, limit: int = 50) -> List[dict]:
    """Load recent JSON run reports from the artifact directory."""
    base_dir = Path(RUN_ARTIFACTS_DIR)
    if not base_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    reports: List[dict] = []
    for path in sorted(base_dir.glob("*/report.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        started_at = report.get("started_at")
        if started_at:
            try:
                started_dt = datetime.fromisoformat(started_at)
            except ValueError:
                started_dt = None
            if started_dt and started_dt < cutoff:
                continue

        reports.append(report)
        if len(reports) >= limit:
            break
    return list(reversed(reports))


def _build_run_markdown(report_dict: dict) -> str:
    lines = [
        f"# MobilityNews Run Report: {report_dict['run_id']}",
        "",
        f"- mode: `{report_dict['mode']}`",
        f"- state: `{report_dict['state']}`",
        f"- started_at: `{report_dict['started_at']}`",
        f"- finished_at: `{report_dict.get('finished_at', '')}`",
    ]

    summary = report_dict.get("summary", {})
    if summary:
        lines.extend(
            [
                "",
                "## Summary",
                *(f"- {key}: {value}" for key, value in summary.items()),
            ]
        )

    source_results = report_dict.get("source_results", [])
    if source_results:
        lines.extend(["", "## Sources"])
        for result in source_results:
            warning_text = f" | warnings={','.join(result.get('warnings', []))}" if result.get("warnings") else ""
            error_text = f" | error={result.get('error_message')}" if result.get("error_message") else ""
            lines.append(
                f"- {result['source_name']}: success={result['success']} | count={result['article_count']}{warning_text}{error_text}"
            )

    watchdog_alerts = report_dict.get("watchdog_alerts", [])
    if watchdog_alerts:
        lines.extend(["", "## Watchdog Alerts", *(f"- {alert}" for alert in watchdog_alerts)])

    qa_result = report_dict.get("qa_result")
    if qa_result:
        lines.extend(["", "## QA", f"- passed: {qa_result.get('passed')}", f"- blocked: {qa_result.get('blocked')}"])
        for finding in qa_result.get("findings", []):
            lines.append(f"- [{finding['severity']}] {finding['code']}: {finding['message']}")

    selected_articles = report_dict.get("selected_articles", [])
    if selected_articles:
        lines.extend(["", "## Selected Articles"])
        for article in selected_articles:
            lines.append(
                f"- [{article.get('source')}] {article.get('translated_title')} ({article.get('category', '기타')})"
            )

    delivery = report_dict.get("delivery_result")
    if delivery:
        lines.extend(
            [
                "",
                "## Delivery",
                f"- success: {delivery.get('success')}",
                f"- subject: {delivery.get('subject')}",
                f"- total_recipients: {delivery.get('total_recipients')}",
            ]
        )
        for batch in delivery.get("batch_results", []):
            lines.append(
                f"- batch {batch['batch_index']}/{batch['total_batches']}: success={batch['success']} | attempts={batch['attempts']} | recipients={len(batch['recipients'])}"
            )

    scout = report_dict.get("scout_suggestions", [])
    if scout:
        lines.extend(["", "## Scout Suggestions"])
        for suggestion in scout:
            lines.append(f"- [{suggestion['kind']}] {suggestion['source_name']}: {suggestion['suggestion']}")

    if report_dict.get("notes"):
        lines.extend(["", "## Notes", *(f"- {note}" for note in report_dict["notes"])])

    if report_dict.get("error_message"):
        lines.extend(["", "## Error", f"- {report_dict['error_message']}"])

    return "\n".join(lines) + "\n"


def save_run_report(report: RunReport) -> None:
    """Write JSON and markdown reports for one run."""
    run_dir = get_run_dir(report.run_id)
    report.artifacts.report_json_path = str(run_dir / "report.json")
    report.artifacts.report_markdown_path = str(run_dir / "report.md")

    report_dict = to_serializable(report)
    Path(report.artifacts.report_json_path).write_text(
        json.dumps(report_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(report.artifacts.report_markdown_path).write_text(
        _build_run_markdown(report_dict),
        encoding="utf-8",
    )


def write_weekly_ops_report(
    run_id: str,
    reports: Iterable[dict],
    suggestions: List[ScoutSuggestion] | None = None,
) -> str:
    """Generate a weekly operational summary markdown file."""
    suggestions = suggestions or []
    reports = list(reports)
    weekly_dir = _ensure_dir(Path(WEEKLY_REPORTS_DIR))
    report_path = weekly_dir / f"weekly_ops_{run_id}.md"

    total_runs = len(reports)
    successful_runs = sum(1 for report in reports if report.get("state") == "SENT")
    blocked_runs = sum(1 for report in reports if report.get("state") == "QA_BLOCKED")
    failed_runs = sum(1 for report in reports if str(report.get("state", "")).startswith("FAILED"))

    source_issues = {}
    for report in reports:
        for result in report.get("source_results", []):
            if result.get("warnings") or not result.get("success", True):
                source_issues[result["source_name"]] = source_issues.get(result["source_name"], 0) + 1

    lines = [
        f"# Weekly MobilityNews Ops Report ({run_id})",
        "",
        "## Run Summary",
        f"- total_runs: {total_runs}",
        f"- successful_runs: {successful_runs}",
        f"- qa_blocked_runs: {blocked_runs}",
        f"- failed_runs: {failed_runs}",
    ]

    if source_issues:
        lines.extend(["", "## Repeated Source Issues"])
        for source_name, count in sorted(source_issues.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- {source_name}: {count}회 문제 감지")

    if suggestions:
        lines.extend(["", "## Scout Suggestions"])
        for suggestion in suggestions:
            lines.append(f"- [{suggestion.kind}] {suggestion.source_name}: {suggestion.suggestion}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(report_path)
