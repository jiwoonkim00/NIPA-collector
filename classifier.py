import json
import logging
import re

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


def classify(title: str, business_name: str) -> dict:
    prompt = PROMPT.format(title=title, business_name=business_name)
    try:
        response = _get_client().models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text.strip()

        # JSON 블록 추출 (마크다운 코드블록 대응)
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError(f"JSON 파싱 실패: {text[:100]}")

        data = json.loads(json_match.group())
        result = data.get("result", "🔍 검토필요")
        score = int(data.get("score", 0))
        reason = data.get("reason", "")

        # result 값 유효성 검증
        valid = {"✅ 관련", "🔍 검토필요", "❌ 무관"}
        if result not in valid:
            logger.warning("알 수 없는 result 값: %s → 검토필요로 대체", result)
            result = "🔍 검토필요"

        return {"result": result, "score": score, "reason": reason}

    except Exception as e:
        logger.error("분류 실패 [%s]: %s", title[:30], e)
        return {"result": "🔍 검토필요", "score": 0, "reason": f"API 오류: {e}"}
