# NIPA 사업공고 자동 수집 Agent

NIPA(nipa.kr) 사업공고 목록을 주기적으로 크롤링하여 Google Sheets에 신규 공고를 자동 추가합니다.

## 파일 구조

```
NIPA_list/
├── main.py            # 실행 진입점
├── scraper.py         # NIPA 페이지 수집 + 파싱
├── sheets_client.py   # Google Sheets 읽기/쓰기
├── config.py          # 환경변수 로딩
├── requirements.txt
├── .env.example       # 환경변수 예시
└── nipa_agent.log     # 실행 로그 (자동 생성)
```

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

1. `.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

2. `.env` 파일에 값 입력:

```
SHEET_ID=스프레드시트_ID        # URL의 /d/ 뒤 문자열
CREDENTIALS_FILE=credentials.json
PAGES_TO_SCAN=3
REQUEST_DELAY=1.0
```

## Google Sheets 서비스 계정 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **Google Sheets API** 및 **Google Drive API** 활성화
3. **서비스 계정** 생성 → JSON 키 파일 다운로드 → `credentials.json`으로 저장
4. Google Sheets 문서를 서비스 계정 이메일에 **편집자** 권한으로 공유
5. Sheets 첫 번째 시트의 1행 헤더는 자동으로 생성됩니다 (수동 추가 불필요)

## 실행

```bash
python main.py
```

실행 결과 예시:
```
[결과] 신규 추가: 5건 / 중복 스킵: 25건 / 실패: 0건
```

## Google Sheets 컬럼 구조

| 열 | 컬럼명 | 설명 |
|----|--------|------|
| A | 수집일시 | 스크립트 실행 시각 |
| B | 공고번호 | 목록 순번 |
| C | 상태/D-day | D-17, 종료, 상시모집 등 |
| D | 공고명 | 공고 제목 |
| E | 사업명 | 관련 사업명 |
| F | 신청기간 시작 | YYYY-MM-DD HH:MM |
| G | 신청기간 종료 | YYYY-MM-DD HH:MM |
| H | 담당자 | 담당자 이름 |
| I | 등록일 | YYYY-MM-DD |
| J | 상세URL | 공고 상세 페이지 링크 |
| K | source_key | 중복 방지용 고유 키 (nipa_{ID}) |
| L | 비고 | 수동 메모용 |

---

## 스케줄링

### Windows 작업 스케줄러 (3시간마다 실행)

**방법 1 — 명령 프롬프트:**
```cmd
schtasks /create /tn "NIPA_Collector" /tr "python C:\절대경로\NIPA_list\main.py" /sc hourly /mo 3 /st 09:00
```

**방법 2 — GUI:**
1. `작업 스케줄러` 앱 실행
2. `작업 만들기` → 이름: `NIPA_Collector`
3. `트리거` 탭 → `새로 만들기` → 매일 반복, `고급 설정`에서 `3시간마다 반복` 체크
4. `동작` 탭 → 프로그램: `python`, 인수: `C:\절대경로\main.py`

---

### GitHub Actions (3시간마다, KST 기준 00/03/06/09/12/15/18/21시)

`.github/workflows/nipa.yml` 파일 생성:

```yaml
name: NIPA Collector

on:
  schedule:
    - cron: '0 */3 * * *'
  workflow_dispatch:  # 수동 실행 허용

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Write credentials
        run: echo '${{ secrets.CREDENTIALS_JSON }}' > credentials.json

      - name: Run collector
        env:
          SHEET_ID: ${{ secrets.SHEET_ID }}
          CREDENTIALS_FILE: credentials.json
        run: python main.py
```

**GitHub Secrets 설정** (Settings → Secrets and variables → Actions):
- `SHEET_ID`: Google Sheets 문서 ID
- `CREDENTIALS_JSON`: `credentials.json` 파일 전체 내용 (JSON 문자열)

---

## 로그 확인

```bash
tail -f nipa_agent.log
```

로그 레벨: INFO (정상), WARNING (행 파싱 실패 등), ERROR (페이지 수집 실패), CRITICAL (Sheets 연결 불가)
