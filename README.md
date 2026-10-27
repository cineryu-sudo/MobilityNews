# MobilityNews

모빌리티 뉴스(국내/해외)를 수집해서, AI로 핵심 기사만 추려 요약하고 이메일 브리핑으로 보내는 Python 프로젝트입니다.

## 프로젝트 개요
- 다중 소스 크롤링: TechCrunch, The Verge, ETNews, AutoDaily, Hacker News, AutoNews
- 기사 전처리:
  - 최근 기사만 사용 (`D-2` 필터)
  - 이미 보낸 기사 URL 중복 제거
- AI 처리:
  - 국내 3건 + 해외 2건 선별
  - 커넥티드카사업팀, AI인포사업팀, FMS솔루션사업팀 관점의 균형 평가
  - 영어 기사 제목 한글 번역
  - 핵심 3개 포인트 + 산업 중요성 + 후속 관찰 포인트 생성
- 결과 전달:
  - `Mobility Business Radar` HTML 이메일 생성
  - Gmail SMTP 발송
- 자동 실행:
  - GitHub Actions 스케줄 실행 (`.github/workflows/daily-briefing.yml`)

## 폴더 구조
```text
MobilityNews/
├─ main.py                  # 실행 엔트리포인트
├─ config.py                # 환경설정/상수
├─ requirements.txt
├─ .env.example
├─ crawlers/                # 뉴스 수집기
├─ intelligence/            # 필터/번역/요약
├─ delivery/                # 이메일 템플릿/발송
└─ .github/workflows/       # 스케줄 배치
```

## 로컬 설치
Windows PowerShell 기준:

```powershell
cd J:\1.Projects\MobilityNews
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## 환경변수 설정
`.env` 파일에 아래 값 입력:

```env
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
RECIPIENT_EMAILS=a@example.com,b@example.com
```

## 실행 방법
테스트 실행(메일 발송 없음):

```powershell
.\.venv\Scripts\python.exe .\main.py --dry-run
```

- 결과:
  - `preview_email.html` 생성
  - `data/runs/<run_id>/report.json`
  - `data/runs/<run_id>/report.md`

실제 발송:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

수동 승인 모드:

```powershell
.\.venv\Scripts\python.exe .\main.py --manual-approval
```

- 결과:
  - 발송 없이 preview 생성
  - `data/runs/<run_id>/approval_draft.json` 저장

승인된 초안 발송:

```powershell
.\.venv\Scripts\python.exe .\main.py --send-approved-draft .\data\runs\<run_id>\approval_draft.json
```

주간 운영 리포트만 생성:

```powershell
.\.venv\Scripts\python.exe .\main.py --weekly-report-only
```

주간 운영 리포트 생성 후 이메일 발송:

```powershell
.\.venv\Scripts\python.exe .\main.py --send-weekly-report
```

- 기본 수신자:
  - `goodnews@lguplus.co.kr`
- 환경변수 `OPS_REPORT_RECIPIENT_EMAILS`로 변경 가능

## GitHub Actions 실행
워크플로우 파일: `.github/workflows/daily-briefing.yml`

- 스케줄 실행 + 수동 실행(`workflow_dispatch`) 지원
- 수동 실행 시 `manual_approval=true`로 승인 초안만 생성 가능
- GitHub Secrets 필요:
  - `ANTHROPIC_API_KEY`
  - `GMAIL_ADDRESS`
  - `GMAIL_APP_PASSWORD`
  - `RECIPIENT_EMAILS`
- 실행 결과 아티팩트:
  - `data/runs/`
  - `data/weekly/`
  - `preview_email.html`

주간 운영 리포트 워크플로우: `.github/workflows/weekly-ops-report.yml`

- 매주 금요일 오전 8시 30분 KST 기준 실행
- 최근 7일 운영 리포트를 생성하고 `goodnews@lguplus.co.kr`로 이메일 발송

## 수정 방법 (빠른 가이드)
자주 수정하는 포인트만 정리합니다.

### 브리핑 V2 콘텐츠 구조
- `TODAY'S SIGNAL`: 전체 기사를 관통하는 모빌리티 사업 신호
- `ORGANIZATION VIEW`: 세 사업팀 관련 기사 커버리지
- `KEY POINTS`: 기사별 핵심 사실 3개
- `WHY IT MATTERS`: 산업 관점의 중요성
- `WATCH NEXT`: 다음으로 확인할 후속 신호

### 1) 수집 소스 추가/수정
- 파일: `crawlers/*.py`
- 기준 클래스: `crawlers/base.py`의 `BaseCrawler`
- 엔트리 연결: `main.py`의 `collect_articles()`

### 2) 기사 선별 개수/기준 변경
- 파일: `config.py`
- 주요 값:
  - `DOMESTIC_COUNT`
  - `INTERNATIONAL_COUNT`
  - `ARTICLE_MAX_AGE_DAYS`
  - `COMPETITOR_KEYWORDS`
  - `MARKET_KEYWORDS`

### 3) 이메일 디자인/카피 수정
- 파일: `delivery/template.py`
- 제목 규칙/발송 로직: `delivery/email_sender.py`

### 4) 중복 발송 정책 변경
- 파일: `main.py`
- 관련 상수: `SENT_HISTORY_FILE`, `HISTORY_RETENTION_DAYS`

## 트러블슈팅
- `401 invalid x-api-key`:
  - `ANTHROPIC_API_KEY` 확인
- 메일 인증 실패:
  - Gmail 앱 비밀번호(`GMAIL_APP_PASSWORD`) 확인
- 기사 0건 수집:
  - 대상 사이트 구조 변경 가능성 높음 → 해당 crawler 선택자 업데이트
