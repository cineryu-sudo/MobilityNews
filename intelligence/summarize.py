"""
Summarization module for generating insights and article summaries.
"""

import logging
import re
from typing import List, Dict
from dataclasses import dataclass, field

import anthropic

from crawlers.base import Article
from config import ANTHROPIC_API_KEY, LLM_MODEL
from intelligence.organization import ORGANIZATION_TEAMS, normalize_related_teams

logger = logging.getLogger(__name__)


@dataclass
class ArticleSummary:
    """Contains summary information for an article."""
    original_title: str
    translated_title: str
    summary: str
    url: str
    source: str
    category: str = ""
    key_points: List[str] = field(default_factory=list)
    why_it_matters: str = ""
    business_implication: str = ""
    related_teams: List[str] = field(default_factory=list)
    watch_point: str = ""

    @property
    def is_cross_team_signal(self) -> bool:
        """Return whether the article is relevant to multiple business teams."""
        return len(set(self.related_teams) & set(ORGANIZATION_TEAMS)) >= 2


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
        1. Executive insight across the mobility business
        2. Structured article briefs for the three business teams
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

[ARTICLE_{i}_RELATED_TEAMS]
관련 조직을 쉼표로 구분하여 1개 이상 선택
(커넥티드카사업팀, AI인포사업팀, FMS솔루션사업팀, 공통 중 복수 선택 가능)

[ARTICLE_{i}_KEY_POINTS]
- 기사 본문에서 확인되는 핵심 사실
- 수치, 기업의 결정, 기술 또는 시장 변화
- 향후 영향을 이해하는 데 필요한 배경

[ARTICLE_{i}_WHY_IT_MATTERS]
이 변화가 모빌리티 산업에서 중요한 이유를 1~2문장으로 작성

[ARTICLE_{i}_WATCH_POINT]
추가로 확인해야 할 다음 신호를 한 문장으로 작성
"""

        prompt = f"""당신은 LG유플러스 모빌리티 조직을 지원하는 수석 산업 애널리스트입니다.
아래 {n}개 기사를 분석하여 경영진과 실무자가 빠르게 판단할 수 있는 브리핑을 작성해주세요.
기사 본문 발췌가 제공된 경우 반드시 해당 내용을 기반으로 요약하세요.

조직 구성:
- 커넥티드카사업팀: 통신 사업, DCM 개발, DCM 운영
- AI인포사업팀: 차량 인포테인먼트 및 AI 기반 차량 경험 사업
- FMS솔루션사업팀: 초정밀측위, 차량 관제 및 운영 솔루션 사업

작성 원칙:
- 세 조직 사이에 우선순위를 두지 마세요.
- 한 기사가 여러 조직과 관련되면 관련 조직을 모두 선택하세요.
- 조직별 사업 전략이나 실행 과제는 추정하지 마세요.
- 기사에 없는 사실이나 사업 기회를 단정적으로 만들어내지 마세요.
- KEY_POINTS는 서로 겹치지 않는 정확히 3개의 불렛으로 작성하세요.

{article_info}

다음 형식으로 작성해주세요:

[EXECUTIVE_INSIGHT]
{n}개 기사를 관통하는 모빌리티 사업 신호를 한 문장으로 작성 (조직장 보고용, 70자 내외)
{article_format}"""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=max(3000, len(articles) * 1000),
                messages=[{"role": "user", "content": prompt}]
            )

            if getattr(response, "stop_reason", None) == "max_tokens":
                raise RuntimeError("구조화 브리핑 응답이 최대 토큰 한도에서 잘렸습니다.")
            
            response_text = response.content[0].text.strip()
            
            # Parse response
            executive_insight = self._clean_prose(
                self._extract_section(response_text, "EXECUTIVE_INSIGHT")
            )
            
            article_summaries = []
            for i, article in enumerate(articles):
                category_text = self._extract_section(response_text, f"ARTICLE_{i+1}_CATEGORY")
                related_teams_text = self._extract_section(response_text, f"ARTICLE_{i+1}_RELATED_TEAMS")
                key_points_text = self._extract_section(response_text, f"ARTICLE_{i+1}_KEY_POINTS")
                why_it_matters = self._clean_prose(
                    self._extract_section(response_text, f"ARTICLE_{i+1}_WHY_IT_MATTERS")
                )
                watch_point = self._clean_prose(
                    self._extract_section(response_text, f"ARTICLE_{i+1}_WATCH_POINT")
                )

                key_points = self._extract_bullets(key_points_text)
                summary_text = " ".join(key_points) if key_points else "요약을 생성할 수 없습니다."

                article_summaries.append(ArticleSummary(
                    original_title=article.title,
                    translated_title=translations.get(article.title, article.title),
                    summary=summary_text or "요약을 생성할 수 없습니다.",
                    url=article.url,
                    source=article.source,
                    category=self._clean_single_line(category_text) or "기타",
                    key_points=key_points,
                    why_it_matters=why_it_matters,
                    related_teams=self._parse_related_teams(related_teams_text),
                    watch_point=watch_point,
                ))
            
            logger.info(f"Generated briefing with {len(article_summaries)} article summaries")
            
            return BriefingResult(
                executive_insight=executive_insight or "오늘의 모빌리티 동향을 분석 중입니다.",
                articles=article_summaries,
            )
            
        except anthropic.AuthenticationError as e:
            # 인증 에러(401)는 절대 fallback 발송하지 않고 파이프라인을 중단시킨다.
            # GitHub Secrets의 ANTHROPIC_API_KEY가 무효/만료된 상황으로,
            # 빈 요약 메일이 발송되는 사고를 막기 위함이다.
            logger.error(f"Summarization auth error (401): {e}")
            raise RuntimeError(
                "Anthropic API 인증 실패(401)로 요약 생성을 중단합니다. "
                "GitHub Secrets의 ANTHROPIC_API_KEY가 유효한지 확인하세요. "
                f"원본 에러: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: create basic summaries (QA 게이트에서 차단됨)
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
                        key_points=[],
                        why_it_matters="",
                        related_teams=[],
                        watch_point="",
                    )
                    for a in articles
                ]
            )

    @staticmethod
    def _clean_single_line(text: str) -> str:
        """Normalize a short LLM section into one plain line."""
        if not text:
            return ""
        line = text.splitlines()[0].strip()
        return re.sub(r"^[-*•\d.)\s]+", "", line).strip()

    @staticmethod
    def _extract_bullets(text: str) -> List[str]:
        """Extract up to three non-empty bullet items from an LLM section."""
        bullets = []
        for line in text.splitlines():
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if cleaned:
                bullets.append(cleaned)
        return bullets[:3]

    @staticmethod
    def _clean_prose(text: str) -> str:
        """Remove response separators while preserving multi-sentence prose."""
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and line.strip() not in {"---", "***"}
        ]
        return " ".join(lines)

    @staticmethod
    def _parse_related_teams(text: str) -> List[str]:
        """Map free-form LLM team labels to the canonical organization names."""
        return normalize_related_teams(text)
    
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
