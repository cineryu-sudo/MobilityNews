"""
Translation module for converting English articles to natural Korean.
Preserves industry terminology (EV, OTA, ADAS, etc.).
"""

import logging
from typing import List, Dict

import anthropic

from crawlers.base import Article
from config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


class Translator:
    """Translates English article titles to natural Korean."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def translate_articles(self, articles: List[Article]) -> Dict[str, str]:
        """
        Translate English article titles to Korean.
        Returns a dict mapping original title to translated title.
        Korean articles are returned as-is.
        """
        translations = {}
        
        # Separate English and Korean articles
        english_articles = [a for a in articles if a.language == "en"]
        
        # Korean articles don't need translation
        for article in articles:
            if article.language == "ko":
                translations[article.title] = article.title
        
        if not english_articles:
            return translations
        
        # Batch translate English articles
        titles_to_translate = "\n".join([
            f"{i+1}. {a.title}"
            for i, a in enumerate(english_articles)
        ])
        
        prompt = f"""당신은 모빌리티/자동차 업계 전문 번역가입니다.
아래 영어 기사 제목들을 자연스러운 한국어로 번역해주세요.

번역 규칙:
1. 자연스러운 한국어 문장으로 번역
2. 업계 용어는 영어 그대로 유지: EV, OTA, ADAS, LiDAR, V2X, MaaS 등
3. 회사명은 영어 그대로 유지: Tesla, Waymo, Uber, GM 등
4. 한국 회사는 한글로: 현대, 기아, 카카오, 티맵 등

영어 제목:
{titles_to_translate}

각 번호에 맞춰 번역된 제목만 출력하세요 (번호 포함):
1. 번역된 제목1
2. 번역된 제목2
..."""

        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse numbered translations
            lines = response_text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Extract number and translation
                if ". " in line:
                    parts = line.split(". ", 1)
                    if len(parts) == 2:
                        try:
                            idx = int(parts[0]) - 1
                            translated = parts[1].strip()
                            if 0 <= idx < len(english_articles):
                                original_title = english_articles[idx].title
                                translations[original_title] = translated
                        except ValueError:
                            continue
            
            # Fallback for any missing translations
            for article in english_articles:
                if article.title not in translations:
                    translations[article.title] = article.title
            
            logger.info(f"Translated {len(english_articles)} article titles")
            return translations
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Fallback: return original titles
            for article in english_articles:
                translations[article.title] = article.title
            return translations
