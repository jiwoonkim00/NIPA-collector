import logging

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_ws_cache = None


def get_worksheet() -> gspread.Worksheet:
    global _ws_cache
    if _ws_cache is not None:
        return _ws_cache
    creds = Credentials.from_service_account_file(config.CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    _ws_cache = client.open_by_key(config.SHEET_ID).sheet1
    return _ws_cache


def ensure_header(ws: gspread.Worksheet):
    first_row = ws.row_values(1)
    if first_row != config.SHEET_COLUMNS:
        ws.insert_row(config.SHEET_COLUMNS, index=1)
        logger.info("헤더 행 추가 완료")


def get_existing_keys() -> set[str]:
    ws = get_worksheet()
    all_values = ws.get_all_values()
    if not all_values:
        return set()

    header = all_values[0]
    try:
        key_col = header.index("source_key")
    except ValueError:
        logger.warning("source_key 컬럼을 헤더에서 찾을 수 없습니다.")
        return set()

    return {row[key_col] for row in all_values[1:] if len(row) > key_col and row[key_col]}


def _row_to_values(item: dict, collected_at: str) -> list:
    return [
        collected_at,
        item.get("number", ""),
        item.get("status", ""),
        item.get("title", ""),
        item.get("business_name", ""),
        item.get("application_start", ""),
        item.get("application_end", ""),
        item.get("manager", ""),
        item.get("registered_date", ""),
        item.get("detail_url", ""),
        item.get("source_key", ""),
        "",  # 비고
    ]


def append_announcements(rows: list[dict], collected_at: str) -> tuple[int, int]:
    ws = get_worksheet()
    ensure_header(ws)

    success = 0
    fail = 0
    for item in rows:
        try:
            values = _row_to_values(item, collected_at)
            ws.append_row(values, value_input_option="USER_ENTERED")
            logger.debug("추가: %s (%s)", item.get("title", ""), item.get("source_key", ""))
            success += 1
        except Exception as e:
            logger.error("행 추가 실패 [%s]: %s", item.get("source_key", ""), e)
            fail += 1
    return success, fail
