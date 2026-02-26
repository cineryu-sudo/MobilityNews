#!/usr/bin/env python3
"""
Mobility Insight Bot - Daily Briefing Agent

Main entry point that orchestrates:
1. News collection from multiple sources
2. LLM-based filtering, translation, and summarization
3. Email delivery of the daily briefing

Usage:
    python main.py              # Full run with email
    python main.py --dry-run    # Test run without email
"""

import sys
import argparse
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


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
    
    # Step 1: Filter to Top 5
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
        # Step 1: Collect articles
        articles = collect_articles()
        
        if not articles:
            logger.error("No articles collected. Exiting.")
            return 1
        
        # Step 2: Process with LLM
        briefing = process_articles(articles)
        
        # Step 3: Send briefing
        success = send_briefing(briefing, dry_run=args.dry_run)
        
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
