import logging
import sys
import time
from datetime import datetime

import config
import classifier
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


def _build_target_row(row: dict, result: dict, classified_at: str) -> list:
    return [
        row.get("수집일시", ""),
        row.get("공고번호", ""),
        row.get("상태/D-day", ""),
        row.get("공고명", ""),
        row.get("사업명", ""),
        row.get("신청기간 시작", ""),
        row.get("신청기간 종료", ""),
        row.get("담당자", ""),
        row.get("등록일", ""),
        row.get("상세URL", ""),
        row.get("source_key", ""),
        result["result"],
        result["score"],
        result["reason"],
        config.GEMINI_MODEL,
        classified_at,
    ]


def _build_log_row(row: dict, result: dict, classified_at: str) -> list:
    return [
        row.get("source_key", ""),
        row.get("공고번호", ""),
        row.get("공고명", ""),
        row.get("사업명", ""),
        row.get("상세URL", ""),
        result["result"],
        result["score"],
        result["reason"],
        config.GEMINI_MODEL,
        classified_at,
    ]


def main():
    setup_logging()
    logger = logging.getLogger("classify")

    try:
        config.validate_classifier()
    except (EnvironmentError, FileNotFoundError) as e:
        print(f"[설정 오류] {e}")
        sys.exit(1)

    classified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=== 의료AI 분류 시작 [%s] ===", classified_at)

    # 전체 공고 읽기
    try:
        all_rows = sheets_client.get_all_rows_as_dicts(config.SOURCE_WORKSHEET_NAME)
        logger.info("전체 공고: %d건", len(all_rows))
    except Exception as e:
        logger.critical("전체_공고 시트 읽기 실패: %s", e)
        sys.exit(1)

    # 이미 분류된 source_key 로드
    classified_keys = sheets_client.get_classified_keys(config.CLASSIFICATION_LOG_WORKSHEET_NAME)
    logger.info("기분류 공고: %d건", len(classified_keys))

    # 미분류 필터링
    unclassified = [
        r for r in all_rows
        if r.get("source_key") and r["source_key"] not in classified_keys
    ]
    logger.info("미분류 공고: %d건", len(unclassified))

    if not unclassified:
        print("\n[분류 결과] 새로 분류할 공고가 없습니다.")
        return

    # 배치 제한 적용
    batch = unclassified[:config.CLASSIFICATION_BATCH_LIMIT]
    logger.info("이번 실행 대상: %d건 (배치 제한: %d)", len(batch), config.CLASSIFICATION_BATCH_LIMIT)

    # 대상 시트 헤더 보장
    sheets_client.ensure_worksheet_header(config.TARGET_WORKSHEET_NAME, config.TARGET_COLUMNS)
    sheets_client.ensure_worksheet_header(config.CLASSIFICATION_LOG_WORKSHEET_NAME, config.LOG_COLUMNS)

    # 분류 실행
    cnt = {"관련": 0, "검토필요": 0, "무관": 0, "실패": 0}
    aborted = False

    for row in batch:
        title = row.get("공고명", "")
        business = row.get("사업명", "")

        try:
            result = classifier.classify(title, business)
        except Exception as e:
            # 429 최대 재시도 실패 또는 기타 오류 → 실행 중단, 로그 미저장
            logger.error("Gemini API 오류로 실행 중단: %s", e)
            print(f"\n[경고] Gemini API 오류로 실행 중단. 이 공고부터 다음 실행 때 재시도됩니다.")
            aborted = True
            break

        # 분류_로그에 항상 기록
        try:
            sheets_client.append_to_worksheet(
                config.CLASSIFICATION_LOG_WORKSHEET_NAME,
                _build_log_row(row, result, classified_at),
            )
        except Exception as e:
            logger.error("로그 기록 실패 [%s]: %s", row.get("source_key", ""), e)
            cnt["실패"] += 1
            continue

        # 관련/검토필요 → 의료AI_관련공고에도 추가
        if result["result"] in ("✅ 관련", "🔍 검토필요"):
            try:
                sheets_client.append_to_worksheet(
                    config.TARGET_WORKSHEET_NAME,
                    _build_target_row(row, result, classified_at),
                )
            except Exception as e:
                logger.error("대상 시트 기록 실패 [%s]: %s", row.get("source_key", ""), e)

        # 카운트
        if result["result"] == "✅ 관련":
            cnt["관련"] += 1
        elif result["result"] == "🔍 검토필요":
            cnt["검토필요"] += 1
        else:
            cnt["무관"] += 1

        logger.debug("%s → %s (%s)", title[:30], result["result"], result["reason"][:40])
        time.sleep(config.CLASSIFICATION_DELAY)

    processed = cnt["관련"] + cnt["검토필요"] + cnt["무관"] + cnt["실패"]
    status = " (중단됨)" if aborted else ""
    print(
        f"\n[분류 결과{status}] 처리: {processed}건 / "
        f"✅관련: {cnt['관련']}건 / "
        f"🔍검토필요: {cnt['검토필요']}건 / "
        f"❌무관: {cnt['무관']}건 / "
        f"실패: {cnt['실패']}건"
    )
    logger.info("=== 분류 완료%s: 처리 %d건 / 관련 %d / 검토필요 %d / 무관 %d / 실패 %d ===",
                status, processed, cnt["관련"], cnt["검토필요"], cnt["무관"], cnt["실패"])


if __name__ == "__main__":
    main()
