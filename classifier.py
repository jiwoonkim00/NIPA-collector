import json
import logging
import re
import time

from google import genai

import config

logger = logging.getLogger(__name__)

PROMPT = """\
다음 NIPA 사업공고가 의료AI 분야와 관련 있는지 판단하세요.

공고명: {title}
사업명: {business_name}

분류 기준:
- ✅ 관련: 의료, 병원, 보건의료, 헬스케어, 디지털헬스, 의료기기, 의료영상, PACS, EMR, \
진단보조, 임상, 환자 데이터, 의료 AI 서비스와 직접 관련 있는 경우
- 🔍 검토필요: AI, 데이터, SW, 디지털전환 사업이지만 의료 분야가 명확하지 않은 경우
- ❌ 무관: 콘텐츠, 제조, 일반 창업, 수출, 교육, 일반 SW 등 의료AI와 직접 관련이 낮은 경우

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"result": "✅ 관련", "score": 85, "reason": "판단 근거를 한 문장으로"}}

result 값은 반드시 "✅ 관련", "🔍 검토필요", "❌ 무관" 중 하나여야 합니다.\
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _parse_response(text: str) -> dict:
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        raise ValueError(f"JSON 파싱 실패: {text[:100]}")
    data = json.loads(json_match.group())
    result = data.get("result", "🔍 검토필요")
    score = int(data.get("score", 0))
    reason = data.get("reason", "")
    valid = {"✅ 관련", "🔍 검토필요", "❌ 무관"}
    if result not in valid:
        logger.warning("알 수 없는 result 값: %s → 검토필요로 대체", result)
        result = "🔍 검토필요"
    return {"result": result, "score": score, "reason": reason}


def classify(title: str, business_name: str) -> dict:
    """분류 결과를 반환한다. 429 한도 초과로 최종 실패 시 예외를 raise한다."""
    prompt = PROMPT.format(title=title, business_name=business_name)

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = _get_client().models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            return _parse_response(response.text.strip())

        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

            if is_rate_limit:
                if attempt < config.MAX_RETRIES:
                    logger.warning(
                        "429 한도 초과 (시도 %d/%d) → %d초 대기 후 재시도",
                        attempt, config.MAX_RETRIES, config.RETRY_WAIT_SECONDS,
                    )
                    time.sleep(config.RETRY_WAIT_SECONDS)
                else:
                    logger.error("429 한도 초과: 최대 재시도 횟수(%d) 도달, 실행 중단", config.MAX_RETRIES)
                    raise
            else:
                logger.error("분류 실패 [%s]: %s", title[:30], e)
                raise
