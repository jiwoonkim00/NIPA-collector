# NIPA 사업공고 자동 수집 및 의료AI 분류 파이프라인

## 프로젝트 개요

정보통신산업진흥원(NIPA)은 매년 수십 건의 IT·AI·SW 분야 지원사업 공고를 게시합니다. 공고는 수시로 올라오며 신청기간이 짧은 경우가 많아, 주기적으로 수동 확인하지 않으면 놓치기 쉽습니다.

이 프로젝트는 두 가지 파이프라인으로 구성됩니다.

1. **수집 파이프라인**: NIPA 공고 목록을 3시간마다 자동 크롤링하여 Google Sheets에 적재
2. **분류 파이프라인**: 수집된 공고를 Gemini LLM으로 의료AI 관련 여부를 자동 판단하여 별도 시트에 분리

GitHub Actions를 통해 클라우드에서 완전 자동 실행되므로 별도 서버나 PC 상시 가동 없이 운영됩니다.

---

## 기본 정보

| 항목 | 내용 |
|------|------|
| **기간** | 2026.02 ~ 현재 (운영 중) |
| **유형** | 개인 프로젝트 |
| **기술 스택** | Python, requests, BeautifulSoup4, gspread, Google Sheets API, Google Gemini API (google-genai), GitHub Actions |
| **레포지토리** | https://github.com/jiwoonkim00/NIPA-collector |

---

## 문제 정의

- NIPA 공고는 수시 업로드되며 신청 마감이 짧게는 2주 이내
- 매번 웹사이트에 직접 접속해 신규 공고를 확인하는 비효율 발생
- 전체 공고 중 의료AI 관련 공고만 추려내는 수작업 필요

**→ 자동 수집 + LLM 분류로 모니터링 및 필터링을 완전히 자동화**

---

## 시스템 아키텍처

```
GitHub Actions (cron: 3시간마다)
        │
        ├── [1단계] main.py  ── 수집 파이프라인
        │         ├── scraper.py     → NIPA 페이지 크롤링 + HTML 파싱
        │         └── sheets_client.py → 신규 공고 시트1(전체_공고) append
        │
        └── [2단계] classify.py  ── 분류 파이프라인
                  ├── sheets_client.py → 시트1에서 미분류 공고 읽기
                  ├── classifier.py   → Gemini API 호출 + 재시도 로직
                  └── sheets_client.py → 결과를 의료AI_관련공고 / 분류_로그에 기록
```

---

## 주요 구현 내용

### 1. HTML 파싱 전략

NIPA 공고 목록 페이지는 **서버사이드 렌더링** 방식으로 JavaScript 없이 HTML에서 데이터를 직접 추출할 수 있습니다. Playwright 같은 헤드리스 브라우저 없이 `requests + BeautifulSoup`만으로 안정적으로 파싱 가능합니다.

```python
rows = soup.select("table.tbgg tbody tr")
```

| 필드 | 셀렉터 |
|------|--------|
| 공고번호 | `td:nth-child(1)` |
| 상태/D-day | `div.point b` |
| 공고명 + URL | `td.tl div.co > div:first-child a` |
| 사업명 | `span.box.bluebox` |
| 신청기간 | `span.bco` |
| 담당자 | `td:nth-child(4) span.bco` |
| 등록일 | `td:nth-child(5) span.bco` |

### 2. 공고 상태 정규화

| CSS 클래스 | 표시값 | 정규화 결과 |
|-----------|--------|------------|
| `point d-one` | `D-17` | `D-17` |
| `point d-day` | `종료` | `종료` |
| `point normal` | `상시<br>모집` | `상시모집` |

`상시모집`의 경우 HTML에 `<br>` 태그가 삽입되어 있어 `.get_text(separator=" ")` 후 정규식 공백 정규화를 적용했습니다.

### 3. 중복 방지 로직

매 실행 시 Google Sheets의 `source_key` 컬럼 전체를 `set`으로 로드하여 O(1) 중복 판단합니다.

```python
source_key = f"nipa_{url_id}"   # 예: nipa_16752
existing_keys = sheets_client.get_existing_keys()
new_items = [i for i in items if i["source_key"] not in existing_keys]
```

URL 내 DB ID를 `source_key`로 사용하여 제목 수정이나 순번 변경에도 안정적입니다.

### 4. Gemini LLM 의료AI 분류

수집된 공고의 공고명과 사업명을 Gemini Flash-Lite에 입력하여 의료AI 관련 여부를 자동 판단합니다.

**분류 기준:**
- `✅ 관련`: 의료, 병원, 보건의료, 헬스케어, 디지털헬스, 의료기기, 의료영상, PACS, EMR, 진단보조, 임상, 환자 데이터 등과 직접 관련
- `🔍 검토필요`: AI·데이터·SW·디지털전환 사업이나 의료 분야가 명확하지 않음
- `❌ 무관`: 콘텐츠, 제조, 일반 창업, 수출, 교육, 일반 SW 등

**프롬프트 설계**: JSON 형식(`result`, `score`, `reason`)으로만 응답하도록 지시하여 파싱 안정성 확보

```python
# 응답 예시
{"result": "✅ 관련", "score": 92, "reason": "AI 기반 의료시스템 디지털 전환 사업으로 의료AI와 직접 관련"}
```

### 5. 분류 파이프라인 안정성

- **배치 제한**: 실행당 최대 N건만 처리 (`CLASSIFICATION_BATCH_LIMIT`)하여 API 한도 관리
- **429 재시도**: Rate Limit 오류 발생 시 `RETRY_WAIT_SECONDS` 대기 후 최대 `MAX_RETRIES`회 재시도
- **중단 시 복구**: 재시도 소진 후 실패한 공고는 `분류_로그`에 저장하지 않아 다음 실행 때 자동 재시도
- **이중 저장 구조**: 모든 분류 결과는 `분류_로그`에 누적, 관련/검토필요만 `의료AI_관련공고`에 별도 저장

### 6. GitHub Actions 자동화

수집(`main.py`) → 분류(`classify.py`) 순서로 동일 워크플로우에서 실행됩니다.

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'
  workflow_dispatch:
```

credentials.json과 GEMINI_API_KEY는 GitHub Repository Secret으로 관리합니다.

---

## Google Sheets 구조

### 시트1 (전체 공고)
수집된 모든 NIPA 공고 원본 데이터

| A: 수집일시 | B: 공고번호 | C: 상태/D-day | D: 공고명 | E: 사업명 | F~G: 신청기간 | H: 담당자 | I: 등록일 | J: 상세URL | K: source_key | L: 비고 |

### 의료AI_관련공고
LLM 분류 결과가 `✅ 관련` 또는 `🔍 검토필요`인 공고

| A~K: 기본정보 | L: 의료AI관련 | M: 관련도점수 | N: 판단근거 | O: 분류모델 | P: 분류일시 |

### 분류_로그
모든 분류 결과 누적 (중복 방지 기준 시트)

| A: source_key | B: 공고번호 | C: 공고명 | D: 사업명 | E: 상세URL | F: 의료AI관련 | G: 관련도점수 | H: 판단근거 | I: 분류모델 | J: 분류일시 |

---

## 성과 및 운영 현황

- 2026년 2월부터 현재까지 **90여 건의 공고 자동 수집 및 관리**
- Gemini LLM 분류로 **의료AI 관련 공고 자동 필터링**, 수동 검토 대상 대폭 축소
- 3시간 주기 자동 실행으로 공고 누락 가능성 최소화
- 운영 중 수동 개입 없이 안정적으로 동작

---

## 트러블슈팅

**`상시모집` 상태가 `상시 모집`으로 깨지는 문제**
- 원인: HTML에 `<b>상시<br>모집</b>` 형태로 줄바꿈 태그가 삽입되어 있음
- 해결: `get_text(separator=" ")` + 정규식 공백 정규화 + 문자열 치환

**신규 공고인데 중복으로 판단되는 문제**
- 원인: 초기 설계 시 순번(377)을 source_key로 사용했으나 재활용 가능성 존재
- 해결: URL 내 DB ID(`/home/2-2/16752` → `16752`)를 source_key로 변경

**Gemini API 429 Rate Limit 오류**
- 원인: Free tier 분당 요청 한도 초과
- 해결: 배치 제한 + 호출 간 대기 시간 설정, 429 감지 시 자동 재시도, 실패 공고 미로깅으로 다음 실행 때 재처리
