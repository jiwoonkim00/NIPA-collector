# NIPA 사업공고 자동 수집 Agent

NIPA(nipa.kr) 사업공고 목록을 3시간마다 크롤링하여 Google Sheets에 신규 공고를 자동 추가합니다.  
GitHub Actions로 클라우드에서 자동 실행되며, PC가 꺼져 있어도 동작합니다.

추가로 `classify.py`를 통해 전체 공고 시트의 미분류 항목을 Gemini로 의료AI 관련성 분류해
`의료AI_관련공고`, `분류_로그` 시트에 적재할 수 있습니다.

## 파일 구조

```
NIPA_list/
├── .github/
│   └── workflows/
│       └── nipa.yml       # GitHub Actions 자동 실행 워크플로우
├── main.py                # 실행 진입점
├── scraper.py             # NIPA 페이지 수집 + 파싱
├── sheets_client.py       # Google Sheets 읽기/쓰기
├── classify.py            # 미분류 공고 의료AI 관련성 분류 실행
├── classifier.py          # Gemini 프롬프트/응답 파싱/재시도 로직
├── config.py              # 환경변수 로딩
├── debug_sheets.py        # 시트 연결/행 조회 디버깅용
├── requirements.txt
├── .env.example           # 환경변수 예시 (로컬 실행용)
└── nipa_agent.log         # 실행 로그 (자동 생성)
```

## Google Sheets 컬럼 구조

| 열 | 컬럼명 | 설명 |
|----|--------|------|
| A | 수집일시 | 스크립트 실행 시각 (YYYY-MM-DD HH:MM:SS) |
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

## GitHub Actions 자동 실행 설정

레포에 이미 워크플로우(`.github/workflows/nipa.yml`)가 포함되어 있습니다.  
아래 두 가지 Secret만 추가하면 바로 작동합니다.

**Settings → Secrets and variables → Actions → Repository secrets → New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `SHEET_ID` | Google Sheets URL의 `/d/` 뒤 ~ `/edit` 앞 문자열 |
| `CREDENTIALS_JSON` | `credentials.json` 파일 전체 내용 텍스트 |

설정 후 **Actions 탭 → NIPA 사업공고 수집 → Run workflow** 로 수동 테스트 가능합니다.

---

## 로컬 실행 (선택)

### 설치

```bash
pip install -r requirements.txt
```

### 환경 설정

```bash
cp .env.example .env
```

`.env` 파일 수정:
```
SHEET_ID=스프레드시트_ID
CREDENTIALS_FILE=credentials.json
PAGES_TO_SCAN=3
REQUEST_DELAY=1.0
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
CLASSIFICATION_DELAY=0.5
CLASSIFICATION_BATCH_LIMIT=10
MAX_RETRIES=3
RETRY_WAIT_SECONDS=60
```

### Google Sheets 서비스 계정 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **Google Sheets API** 및 **Google Drive API** 활성화
3. **서비스 계정** 생성 → JSON 키 파일 다운로드 → `credentials.json`으로 저장
4. Google Sheets 문서를 서비스 계정 이메일에 **편집자** 권한으로 공유

### 실행

```bash
python main.py
```

```
[결과] 신규 추가: 5건 / 중복 스킵: 25건 / 실패: 0건
```

### 의료AI 분류 실행

```bash
python classify.py
```

- `CLASSIFICATION_BATCH_LIMIT` 만큼만 한 번에 분류합니다. (기본 `10`)
- Gemini API `429`(rate limit) 발생 시 `MAX_RETRIES`만큼 재시도하고, 재시도 간 `RETRY_WAIT_SECONDS`만큼 대기합니다.
- 재시도 소진 또는 API 오류가 발생하면 해당 공고부터 실행을 중단하며, 다음 실행 시 다시 시도됩니다.

### 로그 확인

```bash
tail -f nipa_agent.log
```

로그 레벨: `INFO`(정상) / `WARNING`(파싱 실패) / `ERROR`(페이지 수집 실패) / `CRITICAL`(Sheets 연결 불가)

---

## Windows 작업 스케줄러 (로컬 PC 상시 실행 시)

```cmd
schtasks /create /tn "NIPA_Collector" /tr "python C:\절대경로\NIPA_list\main.py" /sc hourly /mo 3 /st 09:00
```
