"""
설정 모듈 (Configuration)

전체 파이프라인에서 사용하는 환경변수, API 키, 크롤링/LLM/이메일 관련
상수를 한 곳에서 관리합니다. .env 파일에서 민감 정보를 분리합니다.
"""

import os
from dotenv import load_dotenv


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_list(name: str, default: str = "") -> list[str]:
    return [
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    ]

# ── .env 파일 로드 ─────────────────────────────────────────────
# 프로젝트 루트의 .env 파일에서 환경변수를 읽어옵니다.
load_dotenv()

# ── API 키 ─────────────────────────────────────────────────────
# Claude LLM 호출에 필요한 Anthropic API 키
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Gmail SMTP 설정 ────────────────────────────────────────────
# 브리핑 이메일 발송에 사용할 Gmail 계정 및 앱 비밀번호
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# 수신자 목록: .env에서 쉼표로 구분된 이메일 주소를 파싱
RECIPIENT_EMAILS = [
    email.strip() 
    for email in os.getenv("RECIPIENT_EMAILS", "").split(",") 
    if email.strip()
]
OPS_REPORT_RECIPIENT_EMAILS = _env_list(
    "OPS_REPORT_RECIPIENT_EMAILS",
    "goodnews@lguplus.co.kr",
)

# ── 뉴스 소스 URL ──────────────────────────────────────────────
# 크롤링 대상 9개 사이트 (해외 6 + 국내 3)
# 각 크롤러 클래스에서 직접 URL을 사용하므로 참조용 목록
NEWS_SOURCES = {
    "techcrunch": "https://techcrunch.com/category/transportation/",
    "theverge": "https://www.theverge.com/transportation",
    "autonews": "https://www.autonews.com/mobility-technology",
    "etnews": "https://www.etnews.com/news/section.html?id1=03",
    "autodaily": "http://www.autodaily.co.kr/news/articleList.html?sc_section_code=S1N1",
    "hackernews": "https://hn.algolia.com/api/v1/search_by_date?query=autonomous&tags=story",
    "telematics_wire": "https://telematicswire.net/feed/",
    "zdnet_korea": "https://feeds.feedburner.com/zdkorea",
    "fleetowner": "https://www.fleetowner.com/technology/rss/",
}

# ── 크롤링 설정 ────────────────────────────────────────────────
REQUEST_TIMEOUT = 10   # HTTP 요청 타임아웃 (초)
REQUEST_DELAY = 1      # 요청 간 대기 시간 (초) - 서버 부하 방지
MAX_ARTICLES_PER_SOURCE = 10  # 소스당 최대 수집 기사 수

# ── LLM 설정 ───────────────────────────────────────────────────
# Claude 모델 및 기사 선별 개수
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
TOP_ARTICLES_COUNT = 5   # 총 기사 수 (하위 호환용)
DOMESTIC_COUNT = 3       # 국내 기사 선별 수 (한국어 소스)
INTERNATIONAL_COUNT = 2  # 해외 기사 선별 수 (영어 소스)

# ── 날짜 필터 설정 ─────────────────────────────────────────────
ARTICLE_MAX_AGE_DAYS = 2  # D-2: 최근 2일 이내 기사만 포함 (오래된 기사 제거)

# ── 중복 발송 방지 설정 ────────────────────────────────────────
# 이전에 발송한 기사 URL을 기록하여 동일 기사 재발송 방지
SENT_HISTORY_FILE = "data/sent_history.json"  # 발송 이력 저장 파일
HISTORY_RETENTION_DAYS = 7                     # URL 이력 보관 기간 (일)
TOPIC_DEDUP_WEEKDAYS = 5                       # 주제 중복 체크 기간 (영업일)

# ── 운영/리포트 설정 ───────────────────────────────────────────
RUN_ARTIFACTS_DIR = os.getenv("RUN_ARTIFACTS_DIR", "data/runs")
WEEKLY_REPORTS_DIR = os.getenv("WEEKLY_REPORTS_DIR", "data/weekly")
QA_MIN_ARTICLE_COUNT = _env_int("QA_MIN_ARTICLE_COUNT", TOP_ARTICLES_COUNT)
WATCHDOG_MIN_TOTAL_ARTICLES = _env_int("WATCHDOG_MIN_TOTAL_ARTICLES", 20)
WATCHDOG_LOW_YIELD_THRESHOLD = _env_int("WATCHDOG_LOW_YIELD_THRESHOLD", 1)
WATCHDOG_ALERT_STREAK = _env_int("WATCHDOG_ALERT_STREAK", 2)
DELIVERY_BATCH_SIZE = _env_int("DELIVERY_BATCH_SIZE", 10)
DELIVERY_MAX_RETRIES = _env_int("DELIVERY_MAX_RETRIES", 2)
DELIVERY_RETRY_DELAY_SECONDS = _env_int("DELIVERY_RETRY_DELAY_SECONDS", 3)
SMTP_TIMEOUT_SECONDS = _env_int("SMTP_TIMEOUT_SECONDS", 60)

# ── 필터링 키워드 ──────────────────────────────────────────────
# 경쟁사 키워드: LLM 필터링 시 관련 기사 우선 선별에 활용
COMPETITOR_KEYWORDS = [
    "현대", "Hyundai", "기아", "Kia",
    "Tmap", "티맵", "카카오", "Kakao", "카카오모빌리티",
    "Tesla", "테슬라", "Waymo", "웨이모",
    "우버", "Uber", "Cruise", "크루즈",
    "네이버", "Naver", "SK", "LG",
    "토요타", "Toyota", "GM", "Ford", "폭스바겐", "Volkswagen",
    "BYD", "비야디", "Rivian", "리비안", "Lucid", "루시드",
]

# 시장 지표 키워드: 모빌리티 업계 핵심 기술/트렌드 관련 용어
MARKET_KEYWORDS = [
    "자율주행", "autonomous", "self-driving",
    "전기차", "EV", "electric vehicle",
    "배터리", "battery", "충전", "charging",
    "MaaS", "mobility as a service",
    "OTA", "V2X", "ADAS",
    "라이다", "LiDAR", "레이더", "radar",
    "모빌리티", "mobility", "transportation",
]
