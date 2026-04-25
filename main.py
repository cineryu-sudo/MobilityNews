#!/usr/bin/env python3
"""
Mobility Insight Bot - Daily Briefing Agent

Operational stages:
1. Source collection + watchdog evaluation
2. Date filter and deduplication
3. LLM-based selection, translation, summarization
4. Pre-send QA gate
5. Delivery, approval-draft, or dry-run reporting

Usage:
    python main.py                           # Full run with email
    python main.py --dry-run                 # Generate preview + run report only
    python main.py --manual-approval         # Save approval draft without sending
    python main.py --send-approved-draft ... # Send a previously approved draft
    python main.py --weekly-report-only      # Generate weekly ops report only
    python main.py --send-weekly-report      # Generate and email weekly ops report
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, List

from config import (
    ANTHROPIC_API_KEY,
    ARTICLE_MAX_AGE_DAYS,
    HISTORY_RETENTION_DAYS,
    OPS_REPORT_RECIPIENT_EMAILS,
    SENT_HISTORY_FILE,
    TOPIC_DEDUP_WEEKDAYS,
)
from crawlers.base import Article
from delivery import EmailSender, EmailTemplate
from intelligence import ArticleFilter, Summarizer, Translator
from ops.models import RunMode, RunReport, RunState, SourceRunResult
from ops.qa import evaluate_briefing
from ops.reporting import (
    build_run_id,
    load_approval_draft,
    load_recent_run_reports,
    save_approval_draft,
    save_run_report,
    write_preview_html,
    write_weekly_ops_report,
)
from ops.scout import build_source_scout_suggestions
from ops.watchdog import evaluate_source_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ensure_llm_configured() -> None:
    """Fail fast when the Anthropic API key is not configured."""
    if ANTHROPIC_API_KEY.strip():
        return

    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add a valid Anthropic API key."
    )


def should_save_history(success: bool, dry_run: bool) -> bool:
    """Only persist send history after a real successful send."""
    return success and not dry_run


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Mobility Insight Bot - Daily Briefing Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate preview and reports without sending email",
    )
    group.add_argument(
        "--manual-approval",
        action="store_true",
        help="Generate preview and approval draft without sending email",
    )
    group.add_argument(
        "--send-approved-draft",
        metavar="PATH",
        help="Send a previously generated approval draft JSON file",
    )
    group.add_argument(
        "--weekly-report-only",
        action="store_true",
        help="Generate weekly ops report without collecting news",
    )
    group.add_argument(
        "--send-weekly-report",
        action="store_true",
        help="Generate weekly ops report and send it by email",
    )
    return parser.parse_args()


def get_weekday_cutoff(n_weekdays: int) -> date:
    """Return the date that is n business days before today."""
    count = 0
    current = date.today()
    while count < n_weekdays:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return current

def load_sent_history() -> dict:
    """Load sent URL/title history from disk."""
    if not os.path.exists(SENT_HISTORY_FILE):
        return {"urls": {}}

    try:
        with open(SENT_HISTORY_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, IOError) as error:
        logger.warning(f"발송 이력 파일 읽기 실패, 초기화합니다: {error}")
        return {"urls": {}}


def save_sent_history(history: dict) -> None:
    """Persist sent history with an atomic replace."""
    dir_path = os.path.dirname(SENT_HISTORY_FILE)
    os.makedirs(dir_path, exist_ok=True)

    tmp_path = SENT_HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, SENT_HISTORY_FILE)
    logger.info(f"발송 이력 저장 완료 ({len(history['urls'])}건)")


def cleanup_old_history(history: dict) -> dict:
    """Drop stale URL and title history."""
    url_cutoff = (date.today() - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    old_count = len(history["urls"])
    history["urls"] = {
        url: sent_date
        for url, sent_date in history["urls"].items()
        if sent_date >= url_cutoff
    }
    removed = old_count - len(history["urls"])
    if removed > 0:
        logger.info(f"오래된 URL 이력 {removed}건 정리 완료")

    title_cutoff = get_weekday_cutoff(TOPIC_DEDUP_WEEKDAYS).isoformat()
    if "titles" in history:
        old_title_count = len(history["titles"])
        history["titles"] = [
            item for item in history["titles"]
            if item.get("date", "") >= title_cutoff
        ]
        removed_titles = old_title_count - len(history["titles"])
        if removed_titles > 0:
            logger.info(f"오래된 제목 이력 {removed_titles}건 정리 완료")

    return history


def update_sent_history(history: dict, article_records: List[dict], sent_date: str) -> None:
    """Record sent articles for URL and topic deduplication."""
    history.setdefault("urls", {})
    history.setdefault("titles", [])

    for article in article_records:
        history["urls"][article["url"]] = sent_date
        history["titles"].append(
            {
                "title": article["original_title"],
                "date": sent_date,
            }
        )


def remove_already_sent(articles: List[Article], history: dict) -> List[Article]:
    """Filter out articles whose URLs were already sent."""
    sent_urls = set(history.get("urls", {}).keys())
    before = len(articles)
    filtered = [article for article in articles if article.url not in sent_urls]
    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"이전 발송 기사 {removed}건 제외")
    return filtered


def remove_duplicate_topics(articles: List[Article], history: dict) -> List[Article]:
    """Filter out articles that overlap with recent sent topics."""
    title_cutoff = get_weekday_cutoff(TOPIC_DEDUP_WEEKDAYS).isoformat()
    recent_titles = [
        item["title"]
        for item in history.get("titles", [])
        if item.get("date", "") >= title_cutoff
    ]

    if not recent_titles:
        logger.info("최근 발송 이력(제목) 없음 → 주제 중복 검사 생략")
        return articles

    logger.info(
        f"최근 {TOPIC_DEDUP_WEEKDAYS} 영업일 이내 발송 기사 "
        f"{len(recent_titles)}건과 주제 중복 검사 시작"
    )
    return ArticleFilter().remove_duplicate_topics(articles, recent_titles)


def filter_by_date(articles: List[Article]) -> List[Article]:
    """Keep only D-ARTICLE_MAX_AGE_DAYS articles; missing dates are preserved."""
    cutoff = date.today() - timedelta(days=ARTICLE_MAX_AGE_DAYS)
    before = len(articles)

    filtered = []
    no_date_count = 0
    for article in articles:
        if article.published_date is None:
            filtered.append(article)
            no_date_count += 1
        elif article.published_date >= cutoff:
            filtered.append(article)

    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"D-{ARTICLE_MAX_AGE_DAYS} 필터: {removed}건 제외 (오래된 기사)")
    if no_date_count > 0:
        logger.warning(f"날짜 정보 없는 기사 {no_date_count}건 → 날짜 필터 우회 (최신으로 간주)")
    return filtered


def build_crawlers():
    """Instantiate all configured crawlers."""
    from crawlers import (
        AutoDailyCrawler,
        AutoHeraldCrawler,
        AutoNewsCrawler,
        DigitalTodayCrawler,
        ETNewsCrawler,
        FleetOwnerCrawler,
        HackerNewsCrawler,
        TechCrunchCrawler,
        TelematicsWireCrawler,
        TheVergeCrawler,
        ZDNetKoreaCrawler,
    )

    return [
        TechCrunchCrawler(),
        TheVergeCrawler(),
        AutoNewsCrawler(),
        ETNewsCrawler(),
        AutoDailyCrawler(),
        HackerNewsCrawler(),
        TelematicsWireCrawler(),
        ZDNetKoreaCrawler(),
        FleetOwnerCrawler(),
        DigitalTodayCrawler(),
        AutoHeraldCrawler(),
    ]


def collect_articles() -> tuple[List[Article], List[SourceRunResult]]:
    """Collect articles and source-level status objects."""
    all_articles: List[Article] = []
    source_results: List[SourceRunResult] = []

    for crawler in build_crawlers():
        logger.info(f"Fetching from {crawler.source_name}...")
        source_result = SourceRunResult(
            source_id=crawler.__class__.__name__,
            source_name=crawler.source_name,
        )

        try:
            articles = crawler.fetch()
            source_result.article_count = len(articles)
            if crawler.last_error:
                source_result.error_message = crawler.last_error
                if len(articles) == 0:
                    source_result.success = False
            all_articles.extend(articles)
            logger.info(f"  → {len(articles)} articles collected")
        except Exception as error:
            source_result.success = False
            source_result.error_message = str(error)
            logger.warning(f"  → Failed: {error}")

        source_results.append(source_result)

    logger.info(f"Total articles collected: {len(all_articles)}")
    return all_articles, source_results


def fetch_article_contents(articles: List[Article]) -> None:
    """Fetch article body snippets for better summarization quality."""
    from crawlers.base import BaseCrawler

    class ContentFetcher(BaseCrawler):
        def __init__(self):
            super().__init__("ContentFetcher", "", "en")

        def fetch(self):
            return []

    fetcher = ContentFetcher()
    for article in articles:
        try:
            content = fetcher.fetch_article_content(article.url)
            if content:
                article.content = content
                logger.info(f"  → 본문 수집 완료: {article.title[:40]}... ({len(content)}자)")
            else:
                logger.warning(f"  → 본문 수집 실패: {article.title[:40]}...")
        except Exception as error:
            logger.warning(f"  → 본문 수집 오류: {article.title[:40]}... ({error})")


def process_articles(articles: List[Article]):
    """Select, translate, and summarize articles."""
    logger.info("Filtering articles...")
    article_filter = ArticleFilter()
    top_articles = article_filter.filter_top_articles(articles)
    logger.info(f"  → Selected {len(top_articles)} top articles")

    logger.info("Fetching article contents...")
    fetch_article_contents(top_articles)

    logger.info("Translating articles...")
    translator = Translator()
    translations = translator.translate_articles(top_articles)
    logger.info(f"  → Translated {len([a for a in top_articles if a.language == 'en'])} English articles")

    logger.info("Generating briefing...")
    summarizer = Summarizer()
    briefing = summarizer.generate_briefing(top_articles, translations)
    logger.info("  → Briefing generated")

    return top_articles, translations, briefing


def build_selected_article_records(selected_articles: List[Article], briefing) -> List[dict]:
    """Combine source article metadata with generated briefing fields."""
    records = []
    for article, summary in zip(selected_articles, briefing.articles):
        records.append(
            {
                "url": article.url,
                "source": article.source,
                "language": article.language,
                "original_title": summary.original_title,
                "translated_title": summary.translated_title,
                "summary": summary.summary,
                "category": summary.category,
            }
        )
    return records


def build_email_html(briefing) -> str:
    """Render the final HTML email."""
    logger.info("Generating HTML email...")
    return EmailTemplate.generate(
        executive_insight=briefing.executive_insight,
        articles=briefing.articles,
        date=datetime.now(),
    )


def log_dry_run_preview(briefing) -> None:
    """Print selected article summaries for dry-run visibility."""
    logger.info("=== PREVIEW MODE ===")
    logger.info(f"Executive Insight: {briefing.executive_insight}")
    logger.info("Articles:")
    for index, article in enumerate(briefing.articles, 1):
        logger.info(f"  {index}. [{article.source}] {article.translated_title}")
        logger.info(f"     {article.summary[:100]}...")


def build_approval_draft(run_id: str, html_content: str, selected_articles: List[dict], preview_path: str) -> dict:
    """Build a manual approval draft payload."""
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "subject": EmailSender.build_subject(),
        "html_content": html_content,
        "articles": selected_articles,
        "preview_html_path": preview_path,
    }


def finalize_run_report(report: RunReport) -> None:
    """Persist the run report and weekly ops report."""
    report.finished_at = datetime.now().isoformat()
    started_at = datetime.fromisoformat(report.started_at)
    finished_at = datetime.fromisoformat(report.finished_at)
    report.summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 1)

    save_run_report(report)
    recent_reports = load_recent_run_reports(days=7, limit=100)
    report.artifacts.weekly_report_path = write_weekly_ops_report(
        report.run_id,
        recent_reports,
        report.scout_suggestions,
    )
    save_run_report(report)


def build_weekly_report_subject() -> str:
    """Build the default weekly ops report subject."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"[MobilityNews Ops Report] {date_str} Weekly Summary"


def send_weekly_report_email(report: RunReport) -> bool:
    """Send the generated weekly ops report to the configured recipients."""
    weekly_report_path = report.artifacts.weekly_report_path
    if not weekly_report_path:
        report.error_message = "Weekly report path not available"
        return False

    if not OPS_REPORT_RECIPIENT_EMAILS:
        report.error_message = "No ops report recipients configured"
        report.notes.append("운영 리포트 수신자 미설정으로 메일 전송을 건너뜀")
        return False

    report_text = Path(weekly_report_path).read_text(encoding="utf-8")
    delivery_result = EmailSender().send_text_report(
        report_text=report_text,
        recipients=OPS_REPORT_RECIPIENT_EMAILS,
        subject=build_weekly_report_subject(),
    )
    report.delivery_result = delivery_result

    if not delivery_result.success:
        report.error_message = delivery_result.error_message
        return False

    report.state = RunState.REPORT_EMAILED
    report.notes.append(
        "주간 운영 리포트를 이메일로 발송했습니다: "
        + ", ".join(OPS_REPORT_RECIPIENT_EMAILS)
    )
    return True


def run_weekly_report_only(send_email: bool = False) -> int:
    """Generate a weekly report, optionally emailing it."""
    run_id = build_run_id()
    report = RunReport(
        run_id=run_id,
        mode=RunMode.SEND_WEEKLY_REPORT if send_email else RunMode.WEEKLY_REPORT_ONLY,
        state=RunState.REPORT_ONLY,
        started_at=datetime.now().isoformat(),
    )
    recent_reports = load_recent_run_reports(days=7, limit=100)
    report.summary["recent_runs"] = len(recent_reports)
    report.scout_suggestions = build_source_scout_suggestions([], recent_reports, [])
    report.notes.append("주간 운영 리포트를 생성했습니다.")

    try:
        finalize_run_report(report)
        logger.info(f"Weekly ops report saved to: {report.artifacts.weekly_report_path}")

        if not send_email:
            return 0

        logger.info("Sending weekly ops report email...")
        if send_weekly_report_email(report):
            save_run_report(report)
            logger.info("Weekly ops report email sent successfully")
            return 0

        report.state = RunState.FAILED_SEND
        save_run_report(report)
        logger.error("Failed to send weekly ops report email")
        return 1
    except KeyboardInterrupt:
        report.state = RunState.INTERRUPTED
        save_run_report(report)
        logger.info("Interrupted by user")
        return 130
    except Exception as error:
        report.state = RunState.FAILED
        report.error_message = str(error)
        save_run_report(report)
        logger.exception(f"Unexpected error while generating weekly report: {error}")
        return 1


def run_approved_draft(draft_path: str) -> int:
    """Send a previously approved draft exactly as saved."""
    run_id = build_run_id()
    report = RunReport(
        run_id=run_id,
        mode=RunMode.APPROVED_DRAFT,
        state=RunState.INITIALIZING,
        started_at=datetime.now().isoformat(),
    )

    try:
        draft = load_approval_draft(draft_path)
        report.selected_articles = draft.get("articles", [])
        report.artifacts.preview_html_path = draft.get("preview_html_path", "")
        report.notes.append(f"승인 초안 발송: {draft_path}")

        report.state = RunState.SENDING
        delivery_result = EmailSender().send(
            draft["html_content"],
            subject=draft.get("subject"),
        )
        report.delivery_result = delivery_result

        if not delivery_result.success:
            report.state = RunState.FAILED_SEND
            report.error_message = delivery_result.error_message
            return 1

        history = cleanup_old_history(load_sent_history())
        update_sent_history(history, report.selected_articles, date.today().isoformat())
        save_sent_history(history)
        report.state = RunState.SENT
        return 0

    except KeyboardInterrupt:
        report.state = RunState.INTERRUPTED
        return 130
    except Exception as error:
        report.state = RunState.FAILED
        report.error_message = str(error)
        logger.exception(f"Unexpected error while sending approved draft: {error}")
        return 1
    finally:
        finalize_run_report(report)


def run_pipeline(mode: str) -> int:
    """Run the main newsletter pipeline."""
    run_id = build_run_id()
    report = RunReport(
        run_id=run_id,
        mode=mode,
        state=RunState.INITIALIZING,
        started_at=datetime.now().isoformat(),
    )
    recent_reports = load_recent_run_reports(days=14, limit=100)

    logger.info("=" * 50)
    logger.info("🚗 Mobility Insight Bot Starting...")
    logger.info("=" * 50)

    try:
        ensure_llm_configured()
        history = cleanup_old_history(load_sent_history())

        report.state = RunState.COLLECTING
        articles, source_results = collect_articles()
        source_results, watchdog_alerts = evaluate_source_results(source_results, recent_reports)
        report.source_results = source_results
        report.watchdog_alerts = watchdog_alerts
        report.summary["articles_collected"] = len(articles)
        report.summary["source_failures"] = sum(1 for result in source_results if not result.success)
        report.summary["source_zero_results"] = sum(1 for result in source_results if result.article_count == 0)

        if not articles:
            raise RuntimeError("No articles collected.")

        report.state = RunState.FILTERING
        articles = filter_by_date(articles)
        report.summary["articles_after_date_filter"] = len(articles)
        logger.info(f"D-{ARTICLE_MAX_AGE_DAYS} 필터 후: {len(articles)}건")

        articles = remove_already_sent(articles, history)
        report.summary["articles_after_url_dedup"] = len(articles)
        logger.info(f"URL 중복 제거 후: {len(articles)}건")

        articles = remove_duplicate_topics(articles, history)
        report.summary["articles_after_topic_dedup"] = len(articles)
        logger.info(f"주제 중복 제거 후: {len(articles)}건")

        if not articles:
            raise RuntimeError("필터링 후 남은 기사가 없습니다.")

        selected_articles, translations, briefing = process_articles(articles)
        report.summary["articles_selected"] = len(selected_articles)
        report.summary["domestic_selected"] = len([a for a in selected_articles if a.language == "ko"])
        report.summary["international_selected"] = len([a for a in selected_articles if a.language == "en"])

        report.selected_articles = build_selected_article_records(selected_articles, briefing)
        report.scout_suggestions = build_source_scout_suggestions(
            source_results,
            recent_reports,
            report.selected_articles,
        )

        html_content = build_email_html(briefing)
        report.artifacts.preview_html_path = write_preview_html(run_id, html_content)
        logger.info(f"HTML preview saved to: {report.artifacts.preview_html_path}")

        report.qa_result = evaluate_briefing(selected_articles, briefing)
        report.summary["qa_findings"] = len(report.qa_result.findings)
        report.summary["watchdog_alerts"] = len(report.watchdog_alerts)

        if report.qa_result.blocked:
            report.state = RunState.QA_BLOCKED
            report.error_message = "Quality gate blocked delivery"
            logger.error("❌ Quality gate blocked delivery")
            return 1

        if mode == RunMode.DRY_RUN:
            log_dry_run_preview(briefing)
            report.state = RunState.DRY_RUN_COMPLETED
            report.notes.append("Dry-run completed without sending email.")
            return 0

        if mode == RunMode.MANUAL_APPROVAL:
            report.artifacts.approval_draft_path = save_approval_draft(
                run_id,
                build_approval_draft(
                    run_id,
                    html_content,
                    report.selected_articles,
                    report.artifacts.preview_html_path,
                ),
            )
            report.state = RunState.WAITING_APPROVAL
            report.notes.append("Manual approval draft generated.")
            logger.info(f"Approval draft saved to: {report.artifacts.approval_draft_path}")
            return 0

        report.state = RunState.SENDING
        logger.info("Sending email...")
        delivery_result = EmailSender().send(html_content)
        report.delivery_result = delivery_result
        report.summary["delivery_recipients"] = delivery_result.total_recipients

        if not delivery_result.success:
            report.state = RunState.FAILED_SEND
            report.error_message = delivery_result.error_message
            logger.error("❌ Failed to send briefing")
            return 1

        if should_save_history(delivery_result.success, mode == RunMode.DRY_RUN):
            update_sent_history(history, report.selected_articles, date.today().isoformat())
            save_sent_history(history)

        report.state = RunState.SENT
        logger.info("✅ Briefing sent successfully!")
        return 0

    except KeyboardInterrupt:
        report.state = RunState.INTERRUPTED
        logger.info("Interrupted by user")
        return 130
    except Exception as error:
        report.state = RunState.FAILED
        report.error_message = str(error)
        logger.exception(f"Unexpected error: {error}")
        return 1
    finally:
        finalize_run_report(report)
        logger.info("=" * 50)
        logger.info(f"🏁 Mobility Insight Bot Complete! state={report.state}")
        logger.info("=" * 50)


def main() -> int:
    """Dispatch to the requested execution mode."""
    args = parse_args()

    if args.send_weekly_report:
        return run_weekly_report_only(send_email=True)
    if args.weekly_report_only:
        return run_weekly_report_only()
    if args.send_approved_draft:
        return run_approved_draft(args.send_approved_draft)
    if args.manual_approval:
        return run_pipeline(RunMode.MANUAL_APPROVAL)
    if args.dry_run:
        return run_pipeline(RunMode.DRY_RUN)
    return run_pipeline(RunMode.LIVE)


if __name__ == "__main__":
    sys.exit(main())
