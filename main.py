import logging
import sys
from datetime import datetime

import config
import scraper
import sheets_client


def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger("main")

    try:
        config.validate()
    except (EnvironmentError, FileNotFoundError) as e:
        print(f"[설정 오류] {e}")
        sys.exit(1)

    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=== NIPA 수집 시작 [%s] ===", collected_at)

    # 1. 기존 source_key 로드
    try:
        existing_keys = sheets_client.get_existing_keys()
        logger.info("기존 등록 공고 수: %d건", len(existing_keys))
    except Exception as e:
        logger.critical("Google Sheets 연결 실패: %s", e)
        sys.exit(1)

    # 2. NIPA 페이지 크롤링
    items = scraper.scrape_pages()
    logger.info("크롤링 완료: 총 %d건", len(items))

    # 3. 신규/중복 분류
    new_items = []
    skipped = 0
    for item in items:
        if item["source_key"] in existing_keys:
            skipped += 1
        else:
            new_items.append(item)

    logger.info("신규: %d건 / 중복 스킵: %d건", len(new_items), skipped)

    # 4. 신규 공고 추가
    added = 0
    failed = 0
    if new_items:
        added, failed = sheets_client.append_announcements(new_items, collected_at)

    # 5. 결과 출력
    print(
        f"\n[결과] 신규 추가: {added}건 / 중복 스킵: {skipped}건 / 실패: {failed}건"
    )
    logger.info("=== 수집 완료: 추가 %d건 / 스킵 %d건 / 실패 %d건 ===", added, skipped, failed)


if __name__ == "__main__":
    main()
