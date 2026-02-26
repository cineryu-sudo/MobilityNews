"""
Configuration module for Mobility Insight Bot.
Loads environment variables and defines constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Gmail Settings
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Recipients (comma-separated in .env)
RECIPIENT_EMAILS = [
    email.strip() 
    for email in os.getenv("RECIPIENT_EMAILS", "").split(",") 
    if email.strip()
]

# News Sources
NEWS_SOURCES = {
    "techcrunch": "https://techcrunch.com/category/transportation/",
    "theverge": "https://www.theverge.com/transportation",
    "autonews": "https://www.autonews.com/mobility-technology",
    "etnews": "https://www.etnews.com/news/section.html?id1=03",
    "autodaily": "http://www.autodaily.co.kr/news/articleList.html?sc_section_code=S1N1",
    "hackernews": "https://hn.algolia.com/api/v1/search_by_date?query=autonomous&tags=story",
}

# Crawling Settings
REQUEST_TIMEOUT = 10  # seconds
REQUEST_DELAY = 1  # seconds between requests
MAX_ARTICLES_PER_SOURCE = 10

# LLM Settings
LLM_MODEL = "claude-sonnet-4-20250514"
TOP_ARTICLES_COUNT = 5

# Competitor Keywords (for filtering)
COMPETITOR_KEYWORDS = [
    "현대", "Hyundai", "기아", "Kia",
    "Tmap", "티맵", "카카오", "Kakao", "카카오모빌리티",
    "Tesla", "테슬라", "Waymo", "웨이모",
    "우버", "Uber", "Cruise", "크루즈",
    "네이버", "Naver", "SK", "LG",
    "토요타", "Toyota", "GM", "Ford", "폭스바겐", "Volkswagen",
    "BYD", "비야디", "Rivian", "리비안", "Lucid", "루시드",
]

# Market Indicator Keywords
MARKET_KEYWORDS = [
    "자율주행", "autonomous", "self-driving",
    "전기차", "EV", "electric vehicle",
    "배터리", "battery", "충전", "charging",
    "MaaS", "mobility as a service",
    "OTA", "V2X", "ADAS",
    "라이다", "LiDAR", "레이더", "radar",
    "모빌리티", "mobility", "transportation",
]
