"""
Article filtering using LLM to select Top 5 relevant articles.
Prioritizes competitor news (70%) and market indicators (30%).
"""

import json
import logging
from typing import List

import anthropic

from crawlers.base import Article
from config import ANTHROPIC_API_KEY, LLM_MODEL, TOP_ARTICLES_COUNT, COMPETITOR_KEYWORDS, MARKET_KEYWORDS

logger = logging.getLogger(__name__)


class ArticleFilter:
    """Filters and ranks articles using LLM based on relevance criteria."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def filter_top_articles(self, articles: List[Article]) -> List[Article]:
        """
        Select top 5 articles prioritizing:
        - 70% competitor-related (현대, Tmap, Kakao, Tesla, etc.)
        - 30% market indicators (자율주행, EV, 배터리, etc.)
        """
        if not articles:
            return []
        
        if len(articles) <= TOP_ARTICLES_COUNT:
            return articles
        
        # Prepare article list for LLM
        article_list = "\n".join([
            f"{i+1}. [{a.source}] {a.title}"
            for i, a in enumerate(articles)
        ])
        
        prompt = f"""당신은 모빌리티 업계 전문 에디터입니다. 
아래 뉴스 기사 목록에서 가장 중요한 {TOP_ARTICLES_COUNT}개를 선정해주세요.

선정 기준:
1. 경쟁사 관련 뉴스 (70% 비중): {', '.join(COMPETITOR_KEYWORDS[:10])} 등
2. 시장 지표/트렌드 (30% 비중): {', '.join(MARKET_KEYWORDS[:10])} 등

기사 목록:
{article_list}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"selected_indices": [1, 2, 3, 4, 5]}}

selected_indices는 위 목록에서 선정한 기사의 번호입니다 (1부터 시작)."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse JSON response
            # Handle potential markdown code blocks
            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            result = json.loads(response_text)
            selected_indices = result.get("selected_indices", [])
            
            # Convert 1-indexed to 0-indexed and filter valid indices
            selected_articles = []
            for idx in selected_indices:
                real_idx = idx - 1
                if 0 <= real_idx < len(articles):
                    selected_articles.append(articles[real_idx])
            
            logger.info(f"Selected {len(selected_articles)} articles from {len(articles)} candidates")
            return selected_articles[:TOP_ARTICLES_COUNT]
            
        except Exception as e:
            logger.error(f"LLM filtering failed: {e}")
            # Fallback: return first N articles
            return articles[:TOP_ARTICLES_COUNT]
