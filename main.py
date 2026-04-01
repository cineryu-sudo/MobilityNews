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

from config import ARTICLE_MAX_AGE_DAYS, SENT_HISTORY_FILE, HISTORY_RETENTION_DAYS, TOPIC_DEDUP_WEEKDAYS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ── 영업일(평일) 계산 헬퍼 ──────────────────────────────────────

def get_weekday_cutoff(n_weekdays: int) -> date:
    """오늘부터 n 영업일(평일, 월~금) 전 날짜를 반환한다.
    예: 오늘이 월요일이고 n=5이면 → 지난 주 월요일
    """
    count = 0
    current = date.today()
    while count < n_weekdays:
        current -= timedelta(days=1)
        if current.weekday() < 5:   # 0=월요일, 4=금요일 (5=토, 6=일은 제외)
            count += 1
    return current


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
    """발송한 기사 URL 이력을 파일에 안전하게 저장한다.

    임시 파일에 먼저 쓴 후 rename하여 쓰기 중 프로세스 중단 시
    파일 손상을 방지한다 (atomic write).
    """
    # data/ 디렉터리가 없으면 생성
    dir_path = os.path.dirname(SENT_HISTORY_FILE)
    os.makedirs(dir_path, exist_ok=True)

    # 임시 파일에 쓴 후 rename (같은 디렉터리여야 atomic)
    tmp_path = SENT_HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, SENT_HISTORY_FILE)
    logger.info(f"발송 이력 저장 완료 ({len(history['urls'])}건)")


def cleanup_old_history(history: dict) -> dict:
    """오래된 이력을 삭제한다.
    - URL 이력: HISTORY_RETENTION_DAYS(7일)보다 오래된 항목 삭제
    - 제목 이력: TOPIC_DEDUP_WEEKDAYS(5 영업일)보다 오래된 항목 삭제
    """
    # URL 이력 정리 (7일 기준)
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

    # 제목 이력 정리 (5 영업일 기준)
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


def remove_already_sent(articles, history: dict):
    """이미 발송된 기사(URL 기준)를 후보 목록에서 제거한다."""
    sent_urls = set(history.get("urls", {}).keys())
    before = len(articles)

    filtered = [a for a in articles if a.url not in sent_urls]

    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"이전 발송 기사 {removed}건 제외")
    return filtered


def remove_duplicate_topics(articles, history: dict) -> list:
    """최근 5 영업일(평일) 내 발송된 기사와 주제/내용이 중복되는 기사를 제거한다.

    sent_history.json의 'titles' 목록과 비교하여
    동일한 사건·발표·제품을 다루는 기사를 LLM으로 식별하고 제외한다.
    """
    from intelligence import ArticleFilter

    # 5 영업일 이내 발송된 기사 제목만 추출
    title_cutoff = get_weekday_cutoff(TOPIC_DEDUP_WEEKDAYS).isoformat()
    recent_titles = [
        item["title"]
        for item in history.get("titles", [])
        if item.get("date", "") >= title_cutoff
    ]

    if not recent_titles:
        logger.info("최근 발송 이력(제목) 없음 → 주제 중복 검사 생략")
        return articles

    logger.info(f"최근 {TOPIC_DEDUP_WEEKDAYS} 영업일 이내 발송 기사 {len(recent_titles)}건과 주제 중복 검사 시작")
    article_filter = ArticleFilter()
    return article_filter.remove_duplicate_topics(articles, recent_titles)


# ── D-2 날짜 필터 ────────────────────────────────────────────────

def filter_by_date(articles) -> list:
    """ARTICLE_MAX_AGE_DAYS(2일) 이내 기사만 남긴다.
    published_date가 None인 기사는 최신으로 간주하여 유지.
    """
    cutoff = date.today() - timedelta(days=ARTICLE_MAX_AGE_DAYS)
    before = len(articles)

    filtered = []
    no_date_count = 0
    for a in articles:
        if a.published_date is None:
            # 날짜 정보 없음 → 최신 페이지에서 수집한 것이므로 유지하되 카운트
            filtered.append(a)
            no_date_count += 1
        elif a.published_date >= cutoff:
            filtered.append(a)
        # else: D-2보다 오래된 기사 → 제외

    removed = before - len(filtered)
    if removed > 0:
        logger.info(f"D-{ARTICLE_MAX_AGE_DAYS} 필터: {removed}건 제외 (오래된 기사)")
    if no_date_count > 0:
        logger.warning(f"날짜 정보 없는 기사 {no_date_count}건 → 날짜 필터 우회 (최신으로 간주)")
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
<<<<<<< HEAD
        TelematicsWireCrawler,
        ZDNetKoreaCrawler,
        FleetOwnerCrawler,
=======
        DigitalTodayCrawler,
        AutoHeraldCrawler,
>>>>>>> 2e15b23 (Add article content crawling, new sources, and critical fixes)
    )

    crawlers = [
        TechCrunchCrawler(),
        TheVergeCrawler(),
        AutoNewsCrawler(),
        ETNewsCrawler(),
        AutoDailyCrawler(),
        HackerNewsCrawler(),
<<<<<<< HEAD
        TelematicsWireCrawler(),
        ZDNetKoreaCrawler(),
        FleetOwnerCrawler(),
=======
        DigitalTodayCrawler(),
        AutoHeraldCrawler(),
>>>>>>> 2e15b23 (Add article content crawling, new sources, and critical fixes)
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


def fetch_article_contents(articles):
    """선정된 기사들의 본문을 크롤링한다 (요약 품질 향상용).

    각 기사 URL에 접속해 본문 텍스트를 최대 500자까지 추출한다.
    실패해도 기사 자체는 유지된다 (본문 없이 제목만으로 요약).
    """
    from crawlers.base import BaseCrawler

    # BaseCrawler의 fetch_article_content 메서드를 사용하기 위한 임시 인스턴스
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
        except Exception as e:
            logger.warning(f"  → 본문 수집 오류: {article.title[:40]}... ({e})")


def process_articles(articles):
    """Filter, translate, and summarize articles using LLM."""
    from intelligence import ArticleFilter, Translator, Summarizer

    # Step 1: Filter (국내 3건 + 해외 2건)
    logger.info("Filtering articles...")
    article_filter = ArticleFilter()
    top_articles = article_filter.filter_top_articles(articles)
    logger.info(f"  → Selected {len(top_articles)} top articles")

    # Step 1.5: 선정된 기사의 본문 크롤링 (요약 품질 향상)
    logger.info("Fetching article contents...")
    fetch_article_contents(top_articles)

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

        # Step 1.6: 이전 발송 기사 제거 (URL 기준 중복 방지)
        articles = remove_already_sent(articles, history)
        logger.info(f"URL 중복 제거 후: {len(articles)}건")

        # Step 1.7: 최근 5 영업일 내 주제 중복 기사 제거
        articles = remove_duplicate_topics(articles, history)
        logger.info(f"주제 중복 제거 후: {len(articles)}건")

        if not articles:
            logger.error("필터링 후 남은 기사가 없습니다. Exiting.")
            return 1

        # Step 2: Process with LLM (국내 3건 + 해외 2건 선정)
        briefing = process_articles(articles)

        # Step 3: Send briefing
        success = send_briefing(briefing, dry_run=args.dry_run)

        # Step 4: 발송한 기사 URL과 제목을 이력에 기록
        if success:
            today_str = date.today().isoformat()
            # titles 키가 없으면 초기화
            if "titles" not in history:
                history["titles"] = []
            for article in briefing.articles:
                # URL 이력: 동일 URL 재발송 방지
                history["urls"][article.url] = today_str
                # 제목 이력: 주제 중복 검사에 사용 (5 영업일 보관)
                history["titles"].append({
                    "title": article.original_title,
                    "date": today_str,
                })
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
