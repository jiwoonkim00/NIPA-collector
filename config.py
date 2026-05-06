import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.nipa.kr"

SHEET_ID = os.environ.get("SHEET_ID", "")
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")
PAGES_TO_SCAN = int(os.environ.get("PAGES_TO_SCAN", "3"))
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "1.0"))
LOG_FILE = os.environ.get("LOG_FILE", "nipa_agent.log")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SOURCE_WORKSHEET_NAME = os.environ.get("SOURCE_WORKSHEET_NAME", "시트1")
TARGET_WORKSHEET_NAME = os.environ.get("TARGET_WORKSHEET_NAME", "의료AI_관련공고")
CLASSIFICATION_LOG_WORKSHEET_NAME = os.environ.get("CLASSIFICATION_LOG_WORKSHEET_NAME", "분류_로그")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
CLASSIFICATION_DELAY = float(os.environ.get("CLASSIFICATION_DELAY", "0.5"))
CLASSIFICATION_BATCH_LIMIT = int(os.environ.get("CLASSIFICATION_BATCH_LIMIT", "10"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_WAIT_SECONDS = int(os.environ.get("RETRY_WAIT_SECONDS", "60"))

SHEET_COLUMNS = [
    "수집일시",
    "공고번호",
    "상태/D-day",
    "공고명",
    "사업명",
    "신청기간 시작",
    "신청기간 종료",
    "담당자",
    "등록일",
    "상세URL",
    "source_key",
    "비고",
]

TARGET_COLUMNS = [
    "수집일시", "공고번호", "상태/D-day", "공고명", "사업명",
    "신청기간 시작", "신청기간 종료", "담당자", "등록일", "상세URL",
    "source_key", "의료AI관련", "관련도점수", "판단근거", "분류모델", "분류일시",
]

LOG_COLUMNS = [
    "source_key", "공고번호", "공고명", "사업명", "상세URL",
    "의료AI관련", "관련도점수", "판단근거", "분류모델", "분류일시",
]


def validate():
    if not SHEET_ID:
        raise EnvironmentError("SHEET_ID가 .env에 설정되지 않았습니다.")
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials 파일을 찾을 수 없습니다: {CREDENTIALS_FILE}"
        )


def validate_classifier():
    validate()
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY가 .env에 설정되지 않았습니다.")
