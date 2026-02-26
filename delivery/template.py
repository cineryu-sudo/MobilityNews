"""
HTML email template for the daily mobility briefing.
"""

from datetime import datetime
from typing import List

from intelligence.summarize import ArticleSummary


class EmailTemplate:
    """Generates HTML email content for the mobility briefing."""
    
    @staticmethod
    def generate(
        executive_insight: str,
        articles: List[ArticleSummary],
        date: datetime = None
    ) -> str:
        """Generate HTML email content."""
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y년 %m월 %d일")
        
        # Generate article cards
        article_cards = ""
        for i, article in enumerate(articles, 1):
            article_cards += f"""
            <div style="background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 16px; border-left: 4px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <span style="background: #3b82f6; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-right: 10px;">{i}</span>
                    <span style="color: #6b7280; font-size: 13px;">{article.source}</span>
                </div>
                <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1f2937; line-height: 1.4;">
                    <a href="{article.url}" style="color: #1f2937; text-decoration: none;">{article.translated_title}</a>
                </h3>
                <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.6;">{article.summary}</p>
                <a href="{article.url}" style="display: inline-block; margin-top: 12px; color: #3b82f6; font-size: 13px; text-decoration: none;">원문 보기 →</a>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobility Daily Briefing</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <div style="max-width: 640px; margin: 0 auto; padding: 20px;">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); border-radius: 16px; padding: 32px; margin-bottom: 24px; text-align: center;">
            <h1 style="margin: 0 0 8px 0; color: white; font-size: 24px; font-weight: 700;">
                🚗 Mobility Daily Briefing
            </h1>
            <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 14px;">{date_str}</p>
        </div>
        
        <!-- Executive Insight -->
        <div style="background: #fef3c7; border-radius: 12px; padding: 24px; margin-bottom: 24px; border-left: 4px solid #f59e0b;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 20px; margin-right: 8px;">💡</span>
                <span style="color: #92400e; font-weight: 600; font-size: 14px;">오늘의 핵심 인사이트</span>
            </div>
            <p style="margin: 0; color: #78350f; font-size: 16px; font-weight: 500; line-height: 1.5;">
                {executive_insight}
            </p>
        </div>
        
        <!-- Articles Section -->
        <div style="margin-bottom: 24px;">
            <h2 style="margin: 0 0 16px 0; color: #1f2937; font-size: 18px; font-weight: 600;">
                📰 Top 5 뉴스
            </h2>
            {article_cards}
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; padding: 24px; color: #9ca3af; font-size: 12px;">
            <p style="margin: 0 0 8px 0;">Mobility Insight Bot으로 자동 생성된 브리핑입니다.</p>
            <p style="margin: 0;">© 2024 Mobility Intelligence</p>
        </div>
        
    </div>
</body>
</html>"""
        
        return html
