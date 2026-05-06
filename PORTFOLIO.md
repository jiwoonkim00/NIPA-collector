# NIPA 사업공고 자동 수집 Agent

## 프로젝트 개요

정보통신산업진흥원(NIPA)은 매년 수십 건의 IT·AI·SW 분야 지원사업 공고를 게시합니다. 공고는 수시로 올라오며 신청기간이 짧은 경우가 많아, 주기적으로 수동 확인하지 않으면 놓치기 쉽습니다.

이 프로젝트는 NIPA 사업공고 목록 페이지를 **3시간마다 자동으로 수집**하고, 신규 공고를 **Google Sheets에 실시간으로 적재**하는 데이터 수집 파이프라인입니다. GitHub Actions를 통해 클라우드에서 자동 실행되므로 별도 서버나 PC 상시 가동 없이 운영됩니다.

---

## 기본 정보

| 항목 | 내용 |
|------|------|
| **기간** | 2026.02 ~ 현재 (운영 중) |
| **유형** | 개인 프로젝트 |
| **기술 스택** | Python, requests, BeautifulSoup4, gspread, Google Sheets API, GitHub Actions |
| **레포지토리** | https://github.com/jiwoonkim00/NIPA-collector |

---

## 문제 정의

- NIPA 공고는 수시 업로드되며 신청 마감이 짧게는 2주 이내
- 매번 웹사이트에 직접 접속해 신규 공고를 확인하는 비효율 발생
- 공고 이력을 체계적으로 관리할 수단이 없어 사후 추적 불가

**→ 자동 수집 및 Google Sheets 적재를 통해 모니터링을 완전히 자동화**

---

## 시스템 아키텍처

```
GitHub Actions (cron: 3시간마다)
        │
        ▼
    main.py  ── 전체 실행 흐름 조율
        │
        ├── scraper.py
        │     ├── NIPA 페이지 HTTP 요청 (requests)
        │     ├── HTML 파싱 (BeautifulSoup4)
        │     └── 공고 데이터 구조화
        │
        └── sheets_client.py
              ├── 기존 source_key 조회 (중복 판단)
              └── 신규 공고 Google Sheets append
```

---

## 주요 구현 내용

### 1. HTML 파싱 전략

NIPA 공고 목록 페이지는 **서버사이드 렌더링** 방식으로 동작하여 JavaScript 없이 HTML에서 데이터를 직접 추출할 수 있습니다. Playwright 같은 헤드리스 브라우저 없이 `requests + BeautifulSoup`만으로 안정적으로 파싱 가능합니다.

```python
# 핵심 셀렉터
rows = soup.select("table.tbgg tbody tr")
```

각 행에서 추출하는 데이터:

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

NIPA 공고의 상태는 세 가지 형태로 표현되며, 각각 다른 CSS 클래스를 가집니다.

| CSS 클래스 | 표시값 | 정규화 결과 |
|-----------|--------|------------|
| `point d-one` | `D-17` | `D-17` |
| `point d-day` | `종료` | `종료` |
| `point normal` | `상시<br>모집` | `상시모집` |

`상시모집`의 경우 HTML에 `<br>` 태그가 포함되어 있어 `.get_text(separator=" ")`로 추출 후 정규식으로 공백을 제거했습니다.

```python
text = re.sub(r"\s+", " ", b_tag.get_text(separator=" ")).strip()
text = text.replace("상시 모집", "상시모집")
```

### 3. 중복 방지 로직

매 실행 시 Google Sheets의 `source_key` 컬럼 전체를 읽어 `set`으로 만든 뒤, 수집된 공고와 비교합니다. O(1) 조회로 효율적인 중복 판단이 가능합니다.

```python
source_key = f"nipa_{url_id}"   # 예: nipa_16752

existing_keys = sheets_client.get_existing_keys()  # set
new_items = [i for i in items if i["source_key"] not in existing_keys]
```

URL 내 DB ID를 `source_key`로 사용하므로, 공고 제목이 수정되거나 순번이 변경되어도 중복 판단이 안정적입니다.

### 4. 신청기간 파싱

신청기간 원문(`"신청기간 : 2026-04-06 13:51 ~ 2026-04-20 23:00"`)에서 시작·종료 일시를 정규식으로 분리하여 각각 별도 컬럼에 저장합니다.

```python
pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})"
```

상시모집 공고는 신청기간이 없어 해당 필드가 비어있으며, 예외 없이 처리됩니다.

### 5. 에러 처리 및 안정성

- **HTTP 요청 실패**: 최대 2회 재시도 후 해당 페이지만 skip, 전체 실행은 계속
- **행 파싱 실패**: 해당 행만 skip + WARNING 로그, 나머지 행 정상 처리
- **Google Sheets 연결 실패**: CRITICAL 로그 후 프로세스 종료
- **크롤링 간격**: 페이지 요청 사이 1초 대기 + User-Agent 헤더 설정

### 6. GitHub Actions 자동화

별도 서버 없이 GitHub의 무료 컴퓨팅 자원을 활용해 3시간마다 자동 실행합니다.

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'
  workflow_dispatch:   # 수동 실행 버튼
```

credentials.json은 GitHub Repository Secret으로 관리하여 민감 정보를 코드에 포함하지 않습니다.

---

## Google Sheets 출력 구조

| 열 | 컬럼명 | 설명 |
|----|--------|------|
| A | 수집일시 | 스크립트 실행 시각 |
| B | 공고번호 | 목록 순번 |
| C | 상태/D-day | D-17, 종료, 상시모집 |
| D | 공고명 | 공고 제목 |
| E | 사업명 | 관련 사업명 |
| F | 신청기간 시작 | YYYY-MM-DD HH:MM |
| G | 신청기간 종료 | YYYY-MM-DD HH:MM |
| H | 담당자 | 담당자 이름 |
| I | 등록일 | YYYY-MM-DD |
| J | 상세URL | 공고 상세 페이지 링크 |
| K | source_key | 중복 방지 고유 키 |
| L | 비고 | 수동 메모용 |

---

## 성과 및 운영 현황

- 2026년 2월부터 현재까지 **90여 건의 공고 자동 수집 및 관리**
- 3시간 주기 자동 실행으로 **공고 누락 가능성 최소화**
- Google Sheets를 데이터 뷰어로 활용해 **필터·정렬·알림 기능** 직접 연계 가능
- 운영 중 수동 개입 없이 안정적으로 동작

---

## 트러블슈팅

**`상시모집` 상태가 `상시 모집`으로 깨지는 문제**
- 원인: HTML에 `<b>상시<br>모집</b>` 형태로 줄바꿈 태그가 삽입되어 있음
- 해결: `get_text(separator=" ")` + 정규식 공백 정규화 + 문자열 치환

**신규 공고인데 중복으로 판단되는 문제**
- 원인: 초기 설계 시 순번(377)을 source_key로 사용했으나, 공고 삭제·재등록 시 순번 재활용 가능성 존재
- 해결: URL 내 DB ID(`/home/2-2/16752` → `16752`)를 source_key로 변경
