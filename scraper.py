import hashlib
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    pass


def fetch_page(page_num: int) -> str:
    url = f"{config.BASE_URL}/home/2-2?curPage={page_num}"
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=config.HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as e:
            if attempt < 2:
                logger.warning("페이지 %d 요청 실패 (시도 %d/3): %s", page_num, attempt + 1, e)
                time.sleep(1)
            else:
                raise ScraperError(f"페이지 {page_num} 수집 실패: {e}") from e


def _normalize_status(b_tag) -> str:
    text = b_tag.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    # "상시 모집" → "상시모집"
    text = text.replace("상시 모집", "상시모집")
    return text


def _parse_application_period(raw: str) -> tuple[str, str]:
    pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})"
    m = re.search(pattern, raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def _parse_row(tr) -> dict | None:
    try:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            return None

        # 공고번호 (순번)
        number = tds[0].get_text(strip=True)

        # 상태
        point_div = tds[1].find("div", class_="point")
        b_tag = point_div.find("b") if point_div else None
        status = _normalize_status(b_tag) if b_tag else tds[1].get_text(strip=True)

        # 공고명 + 링크
        a_tag = tds[2].select_one("div.co > div:first-child a")
        if not a_tag:
            return None
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")
        detail_url = href if href.startswith("http") else config.BASE_URL + href
        url_id = href.rstrip("/").split("/")[-1] if href else ""

        # source_key
        if url_id:
            source_key = f"nipa_{url_id}"
        else:
            source_key = "nipa_" + hashlib.md5(detail_url.encode()).hexdigest()[:12]

        # 사업명
        bluebox = tds[2].select_one("span.box.bluebox")
        business_name = bluebox.get_text(strip=True) if bluebox else ""

        # 신청기간
        bco_spans = tds[2].select("span.bco")
        period_raw = bco_spans[0].get_text(strip=True) if bco_spans else ""
        app_start, app_end = _parse_application_period(period_raw)

        # 담당자
        manager_span = tds[3].find("span", class_="bco")
        manager = manager_span.get_text(strip=True) if manager_span else tds[3].get_text(strip=True)

        # 등록일
        date_span = tds[4].find("span", class_="bco")
        registered_date = date_span.get_text(strip=True) if date_span else tds[4].get_text(strip=True)

        return {
            "number": number,
            "status": status,
            "title": title,
            "detail_url": detail_url,
            "url_id": url_id,
            "source_key": source_key,
            "business_name": business_name,
            "application_period_raw": period_raw,
            "application_start": app_start,
            "application_end": app_end,
            "manager": manager,
            "registered_date": registered_date,
        }
    except Exception as e:
        logger.warning("행 파싱 실패: %s", e)
        return None


def parse_announcements(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.tbgg tbody tr")
    results = []
    for tr in rows:
        item = _parse_row(tr)
        if item:
            results.append(item)
    return results


def scrape_pages(pages: int = None) -> list[dict]:
    if pages is None:
        pages = config.PAGES_TO_SCAN
    all_items = []
    for page_num in range(1, pages + 1):
        try:
            html = fetch_page(page_num)
            items = parse_announcements(html)
            logger.info("페이지 %d: %d건 수집", page_num, len(items))
            all_items.extend(items)
        except ScraperError as e:
            logger.error("페이지 %d 스킵: %s", page_num, e)
        if page_num < pages:
            time.sleep(config.REQUEST_DELAY)
    return all_items
