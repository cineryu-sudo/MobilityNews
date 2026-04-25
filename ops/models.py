"""
Shared operational models for run-state tracking and reporting.
"""

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List


class RunState:
    """Lifecycle states for a newsletter run."""

    INITIALIZING = "INITIALIZING"
    COLLECTING = "COLLECTING"
    FILTERING = "FILTERING"
    QA_BLOCKED = "QA_BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SENDING = "SENDING"
    SENT = "SENT"
    DRY_RUN_COMPLETED = "DRY_RUN_COMPLETED"
    REPORT_ONLY = "REPORT_ONLY"
    REPORT_EMAILED = "REPORT_EMAILED"
    FAILED_SEND = "FAILED_SEND"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class RunMode:
    """Execution mode for a newsletter run."""

    LIVE = "live"
    DRY_RUN = "dry_run"
    MANUAL_APPROVAL = "manual_approval"
    APPROVED_DRAFT = "approved_draft"
    WEEKLY_REPORT_ONLY = "weekly_report_only"
    SEND_WEEKLY_REPORT = "send_weekly_report"


@dataclass
class SourceRunResult:
    """Result of fetching one source during a run."""

    source_id: str
    source_name: str
    article_count: int = 0
    success: bool = True
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class QaFinding:
    """One quality finding raised by the pre-send QA gate."""

    severity: str
    code: str
    message: str


@dataclass
class QaResult:
    """Outcome of the quality gate."""

    passed: bool
    blocked: bool
    findings: List[QaFinding] = field(default_factory=list)


@dataclass
class DeliveryBatchResult:
    """Delivery status for one recipient batch."""

    batch_index: int
    total_batches: int
    recipients: List[str]
    success: bool
    attempts: int = 0
    error_message: str = ""


@dataclass
class DeliveryResult:
    """Overall delivery outcome."""

    success: bool
    subject: str
    total_recipients: int
    batch_results: List[DeliveryBatchResult] = field(default_factory=list)
    error_message: str = ""


@dataclass
class ScoutSuggestion:
    """Source-scout recommendation or weekly coverage suggestion."""

    kind: str
    source_name: str
    reason: str
    suggestion: str


@dataclass
class RunArtifacts:
    """Filesystem artifacts generated during a run."""

    preview_html_path: str = ""
    report_json_path: str = ""
    report_markdown_path: str = ""
    approval_draft_path: str = ""
    weekly_report_path: str = ""


@dataclass
class RunReport:
    """Serializable report for one execution."""

    run_id: str
    mode: str
    state: str
    started_at: str
    finished_at: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    source_results: List[SourceRunResult] = field(default_factory=list)
    watchdog_alerts: List[str] = field(default_factory=list)
    qa_result: QaResult | None = None
    delivery_result: DeliveryResult | None = None
    scout_suggestions: List[ScoutSuggestion] = field(default_factory=list)
    selected_articles: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: RunArtifacts = field(default_factory=RunArtifacts)
    notes: List[str] = field(default_factory=list)
    error_message: str = ""


def to_serializable(value: Any) -> Any:
    """Convert nested dataclasses and common Python objects to JSON-safe values."""
    if is_dataclass(value):
        return {
            field_.name: to_serializable(getattr(value, field_.name))
            for field_ in fields(value)
        }

    if isinstance(value, dict):
        return {str(key): to_serializable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_serializable(item) for item in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    return value
