#!/usr/bin/env python3
"""
Mobility Insight Bot - Daily Briefing Agent

Main entry point that orchestrates:
1. News collection from multiple sources
2. D-2 date filter + deduplication (중복 기사 제거)
3. LLM-based filtering (국내 3건 + 해외 2건), translation, and summarization
4. Email delivery of the daily briefing

Usage:
    python main.py              # Full run with email
    python main.py --dry-run    # Test run without email
"""

import sys
import json
import os
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import List

from config import (
    ANTHROPIC_API_KEY,
    ARTICLE_MAX_AGE_DAYS,
    SENT_HISTORY_FILE,
    HISTORY_RETENTION_DAYS,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
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


# ── 발송 이력 관리 (중복 기사 방지) ──────────────────────────────

def load_sent_history() -> dict:
    """이전에 발송한 기사 URL 이력을 파일에서 불러온다.
    형식: {"urls": {"https://...": "2026-03-04", ...}}
    """
    if not os.path.exists(SENT_HISTORY_FILE):
        return {"urls": {}}

    try:
        with open(SENT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"발송 이력 파일 읽기 실패, 초기화합니다: {e}")
        return {"urls": {}}


def save_sent_history(history: dict):
    """발송한 기사 URL 이력을 파일에 저장한다."""
    # data/ 디렉터리가 없으면 생성
    os.makedirs(os.path.dirname(SENT_HISTORY_FILE), exist_ok=True)

    with open(SENT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"발송 이력 저장 완료 ({len(history['urls'])}건)")


def cleanup_old_history(history: dict) -> dict:
    """HISTORY_RETENTION_DAYS(7일)보다 오래된 이력을 삭제한다."""
    cutoff = (date.today() - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    old_count = len(history["urls"])

    history["urls"] = {
        url: sent_date
        for url, sent_date in history["urls"].items()
        if sent_date >= cutoff
    }

    removed = old_count - len(history["urls"])
    if removed > 0:
        logger.info(f"오래된 이력 {removed}건 정리 완료")
    return history


def remove_already_sent(articles, history: dict):
    """이미 발송된 기사를 후보 목록에서 제거한다."""
    sent_urls = set(history.get("urls", {}).keys())
    before = len(articles)

    filtered = [a for a in articles if a.url not in sent_urls]

    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"이전 발송 기사 {removed}건 제외")
    return filtered


# ── D-2 날짜 필터 ────────────────────────────────────────────────

def filter_by_date(articles) -> list:
    """ARTICLE_MAX_AGE_DAYS(2일) 이내 기사만 남긴다.
    published_date가 None인 기사는 최신으로 간주하여 유지.
    """
    cutoff = date.today() - timedelta(days=ARTICLE_MAX_AGE_DAYS)
    before = len(articles)

    filtered = []
    for a in articles:
        if a.published_date is None:
            # 날짜 정보 없음 → 최신 페이지에서 수집한 것이므로 유지
            filtered.append(a)
        elif a.published_date >= cutoff:
            filtered.append(a)
        # else: D-2보다 오래된 기사 → 제외

    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"D-{ARTICLE_MAX_AGE_DAYS} 필터: {removed}건 제외 (오래된 기사)")
    return filtered


# ── 기존 파이프라인 함수들 ────────────────────────────────────────

def collect_articles():
    """Collect articles from all configured news sources."""
    from crawlers import (
        TechCrunchCrawler,
        TheVergeCrawler,
        AutoNewsCrawler,
        ETNewsCrawler,
        AutoDailyCrawler,
        HackerNewsCrawler,
    )

    crawlers = [
        TechCrunchCrawler(),
        TheVergeCrawler(),
        AutoNewsCrawler(),
        ETNewsCrawler(),
        AutoDailyCrawler(),
        HackerNewsCrawler(),
    ]

    all_articles = []

    for crawler in crawlers:
        try:
            logger.info(f"Fetching from {crawler.source_name}...")
            articles = crawler.fetch()
            all_articles.extend(articles)
            logger.info(f"  → {len(articles)} articles collected")
        except Exception as e:
            logger.warning(f"  → Failed: {e}")
            continue

    logger.info(f"Total articles collected: {len(all_articles)}")
    return all_articles


def process_articles(articles):
    """Filter, translate, and summarize articles using LLM."""
    from intelligence import ArticleFilter, Translator, Summarizer

    # Step 1: Filter (국내 3건 + 해외 2건)
    logger.info("Filtering articles...")
    article_filter = ArticleFilter()
    top_articles = article_filter.filter_top_articles(articles)
    logger.info(f"  → Selected {len(top_articles)} top articles")

    # Step 2: Translate English articles
    logger.info("Translating articles...")
    translator = Translator()
    translations = translator.translate_articles(top_articles)
    logger.info(f"  → Translated {len([a for a in top_articles if a.language == 'en'])} English articles")

    # Step 3: Generate summaries
    logger.info("Generating briefing...")
    summarizer = Summarizer()
    briefing = summarizer.generate_briefing(top_articles, translations)
    logger.info("  → Briefing generated")

    return briefing


def send_briefing(briefing, dry_run=False):
    """Generate HTML email and send to recipients."""
    from delivery import EmailTemplate, EmailSender

    # Generate HTML
    logger.info("Generating HTML email...")
    html_content = EmailTemplate.generate(
        executive_insight=briefing.executive_insight,
        articles=briefing.articles,
        date=datetime.now()
    )

    if dry_run:
        logger.info("=== DRY RUN MODE ===")
        logger.info(f"Executive Insight: {briefing.executive_insight}")
        logger.info("Articles:")
        for i, article in enumerate(briefing.articles, 1):
            logger.info(f"  {i}. [{article.source}] {article.translated_title}")
            logger.info(f"     {article.summary[:100]}...")

        # Save HTML to file for preview
        preview_path = "preview_email.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML preview saved to: {preview_path}")
        return True

    # Send email
    logger.info("Sending email...")
    sender = EmailSender()
    success = sender.send(html_content)

    if success:
        logger.info("✅ Briefing sent successfully!")
    else:
        logger.error("❌ Failed to send briefing")

    return success


# ── 메인 실행 ─────────────────────────────────────────────────────

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Mobility Insight Bot - Daily Briefing Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test run without sending email (saves preview to file)"
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("🚗 Mobility Insight Bot Starting...")
    logger.info("=" * 50)

    try:
        ensure_llm_configured()

        # Step 0: 발송 이력 불러오기 + 오래된 이력 정리
        history = load_sent_history()
        history = cleanup_old_history(history)

        # Step 1: Collect articles
        articles = collect_articles()

        if not articles:
            logger.error("No articles collected. Exiting.")
            return 1

        # Step 1.5: D-2 날짜 필터 (2일 이내 기사만)
        articles = filter_by_date(articles)
        logger.info(f"D-{ARTICLE_MAX_AGE_DAYS} 필터 후: {len(articles)}건")

        # Step 1.6: 이전 발송 기사 제거 (중복 방지)
        articles = remove_already_sent(articles, history)
        logger.info(f"중복 제거 후: {len(articles)}건")

        if not articles:
            logger.error("필터링 후 남은 기사가 없습니다. Exiting.")
            return 1

        # Step 2: Process with LLM (국내 3건 + 해외 2건 선정)
        briefing = process_articles(articles)

        # Step 3: Send briefing
        success = send_briefing(briefing, dry_run=args.dry_run)

        # Step 4: 발송한 기사 URL을 이력에 기록
        if should_save_history(success, args.dry_run):
            today_str = date.today().isoformat()
            for article in briefing.articles:
                history["urls"][article.url] = today_str
            save_sent_history(history)

        logger.info("=" * 50)
        logger.info("🏁 Mobility Insight Bot Complete!")
        logger.info("=" * 50)

        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
