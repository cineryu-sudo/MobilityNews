"""
Summarization module for generating insights and article summaries.
"""

import logging
from typing import List, Dict
from dataclasses import dataclass

import anthropic

from crawlers.base import Article
from config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


@dataclass
class ArticleSummary:
    """Contains summary information for an article."""
    original_title: str
    translated_title: str
    summary: str  # 3-5 sentence summary
    url: str
    source: str
    category: str = ""  # e.g. 전기차, 자율주행, MaaS, 배터리, 플랫폼


@dataclass
class BriefingResult:
    """Complete briefing result with insight and article summaries."""
    executive_insight: str  # 1-sentence insight for leadership
    articles: List[ArticleSummary]


class Summarizer:
    """Generates executive insights and article summaries."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def generate_briefing(
        self, 
        articles: List[Article], 
        translations: Dict[str, str]
    ) -> BriefingResult:
        """
        Generate complete briefing with:
        1. Executive insight (1 sentence summarizing all 5 articles)
        2. Per-article summaries (3 sentences each)
        """
        if not articles:
            return BriefingResult(
                executive_insight="오늘 수집된 기사가 없습니다.",
                articles=[]
            )
        
        # Prepare article list for LLM (본문이 있으면 함께 전달)
        article_info = "\n\n".join([
            f"[기사 {i+1}]\n출처: {a.source}\n제목: {translations.get(a.title, a.title)}\nURL: {a.url}"
            + (f"\n본문 발췌: {a.content}" if a.content else "")
            for i, a in enumerate(articles)
        ])
        
        # 기사 수에 맞게 프롬프트를 동적으로 생성
        n = len(articles)
        article_format = ""
        for i in range(1, n + 1):
            article_format += f"""
[ARTICLE_{i}_CATEGORY]
카테고리를 하나만 선택 (전기차, 자율주행, MaaS, 배터리, 플랫폼, 커넥티드카, 수소차, 충전인프라, 정책/규제, 기타 중 택1)

[ARTICLE_{i}_SUMMARY]
3~5문장으로 핵심 내용을 상세히 요약 (배경, 핵심 사실, 의미/전망 포함)
"""

        prompt = f"""당신은 모빌리티 업계 수석 애널리스트입니다.
아래 {n}개 기사를 분석하여 경영진/팀원 브리핑을 작성해주세요.
기사 본문 발췌가 제공된 경우 반드시 해당 내용을 기반으로 요약하세요.

{article_info}

다음 형식으로 작성해주세요:

[EXECUTIVE_INSIGHT]
{n}개 기사를 관통하는 핵심 인사이트를 한 문장으로 작성 (조직장 보고용, 50자 내외)
{article_format}"""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse response
            executive_insight = self._extract_section(response_text, "EXECUTIVE_INSIGHT")
            
            article_summaries = []
            for i, article in enumerate(articles):
                summary_text = self._extract_section(response_text, f"ARTICLE_{i+1}_SUMMARY")
                category_text = self._extract_section(response_text, f"ARTICLE_{i+1}_CATEGORY")

                article_summaries.append(ArticleSummary(
                    original_title=article.title,
                    translated_title=translations.get(article.title, article.title),
                    summary=summary_text or "요약을 생성할 수 없습니다.",
                    url=article.url,
                    source=article.source,
                    category=category_text or "기타",
                ))
            
            logger.info(f"Generated briefing with {len(article_summaries)} article summaries")
            
            return BriefingResult(
                executive_insight=executive_insight or "오늘의 모빌리티 동향을 분석 중입니다.",
                articles=article_summaries,
            )
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: create basic summaries
            return BriefingResult(
                executive_insight="브리핑 생성 중 오류가 발생했습니다.",
                articles=[
                    ArticleSummary(
                        original_title=a.title,
                        translated_title=translations.get(a.title, a.title),
                        summary="기사 요약을 생성할 수 없습니다.",
                        url=a.url,
                        source=a.source,
                        category="기타",
                    )
                    for a in articles
                ]
            )
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract content from a labeled section."""
        start_marker = f"[{section_name}]"
        
        if start_marker not in text:
            return ""
        
        start_idx = text.index(start_marker) + len(start_marker)
        
        # Find next section or end of text
        end_idx = len(text)
        for marker in ["[EXECUTIVE", "[ARTICLE_"]:
            next_idx = text.find(marker, start_idx)
            if next_idx != -1 and next_idx < end_idx:
                end_idx = next_idx
        
        return text[start_idx:end_idx].strip()
