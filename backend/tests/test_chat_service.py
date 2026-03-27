"""
chat_service 단위 테스트

테스트 범위:
- _has_cjk()          : CJK 감지 (한글 오탐 없음 포함)
- _strip_cjk()        : regex 기반 CJK 제거
- _is_instruction_leak(): 지시문 노출 감지
- _is_korean_rewrite_request(): 한국어 재작성 요청 감지
- _last_assistant_content()   : 이전 AI 답변 추출
- 회귀 케이스: 내부 지시문이 사용자에게 노출되지 않는 입력 패턴 확인

실행 방법:
    cd backend
    python -m pytest tests/test_chat_service.py -v
"""

import pytest

from app.services.chat_service import (
    _has_cjk,
    _is_instruction_leak,
    _is_korean_rewrite_request,
    _last_assistant_content,
    _strip_cjk,
)
from app.schemas.chat import ChatMessage


# ── _has_cjk ──────────────────────────────────────────────────────────────────

class TestHasCjk:
    def test_chinese_detected(self):
        assert _has_cjk("这是中文") is True

    def test_mixed_korean_chinese_detected(self):
        assert _has_cjk("자임추모공원(紫荒追慕公园)은 어디에 있나요?") is True

    def test_pure_korean_not_detected(self):
        assert _has_cjk("자임추모공원의 위치는 문서에서 확인할 수 없습니다.") is False

    def test_empty_string(self):
        assert _has_cjk("") is False

    def test_english_not_detected(self):
        assert _has_cjk("The location is unknown.") is False

    def test_japanese_kanji_detected(self):
        assert _has_cjk("東京に行きます") is True

    def test_hangul_jamo_not_detected(self):
        # 한글 자모(U+3130-318F)는 CJK 범위가 아님
        assert _has_cjk("ㄱㄴㄷ") is False


# ── _strip_cjk ────────────────────────────────────────────────────────────────

class TestStripCjk:
    def test_removes_chinese(self):
        result = _strip_cjk("자임추모공원(紫荒追慕公园)은 서울에 있습니다.")
        assert "紫" not in result
        assert "자임추모공원" in result
        assert "서울에 있습니다" in result

    def test_pure_korean_unchanged(self):
        text = "문서에서 확인할 수 없습니다."
        assert _strip_cjk(text) == text

    def test_cleans_extra_spaces(self):
        # CJK 제거 후 연속 공백 정리 확인
        result = _strip_cjk("위치는 漢字漢字漢字 서울입니다.")
        assert "  " not in result  # 이중 공백 없음

    def test_empty_string(self):
        assert _strip_cjk("") == ""


# ── _is_instruction_leak ──────────────────────────────────────────────────────

class TestIsInstructionLeak:
    """
    모델이 재작성 지시문을 그대로 출력하는 오류 케이스를 감지하는지 확인합니다.
    실제 발생한 버그 케이스: "중국어 대신 한국어로 답변해주세요"
    """

    def test_detects_actual_bug_case(self):
        # 실제 보고된 오류 케이스
        leaked = "문서에서는 자임 추모공원의 정확한 위치는 어디인가요? 중국어 대신 한국어로 답변해주세요."
        assert _is_instruction_leak(leaked) is True

    def test_detects_haejuseyo(self):
        assert _is_instruction_leak("한국어로 답변해 주세요.") is True

    def test_detects_jabseyo(self):
        assert _is_instruction_leak("작성해 주세요.") is True

    def test_normal_answer_not_leaked(self):
        normal = "자임추모공원의 위치는 문서에서 직접 확인되지 않습니다."
        assert _is_instruction_leak(normal) is False

    def test_normal_korean_sentence_not_leaked(self):
        normal = "문서에 따르면 해당 공원은 경기도 소재로 추정됩니다."
        assert _is_instruction_leak(normal) is False


# ── _is_korean_rewrite_request ────────────────────────────────────────────────

class TestIsKoreanRewriteRequest:
    def test_basic_request(self):
        assert _is_korean_rewrite_request("한국어로 다시 말해줘") is True

    def test_hangul_version(self):
        assert _is_korean_rewrite_request("한글로 바꿔줘") is True

    def test_only_korean_request(self):
        assert _is_korean_rewrite_request("한국어로만 작성해줘") is True

    def test_regular_question_not_matched(self):
        # 회귀: 일반 질문은 재작성 요청으로 감지되면 안 됨
        assert _is_korean_rewrite_request("자임추모공원의 위치는 어디지?") is False

    def test_time_question_not_matched(self):
        # 회귀: 시점 관련 일반 질문
        assert _is_korean_rewrite_request("언제부터 이런 상황이 시작됐어?") is False

    def test_no_lang_trigger(self):
        assert _is_korean_rewrite_request("다시 설명해줘") is False

    def test_no_action(self):
        assert _is_korean_rewrite_request("한국어로 된 내용은?") is False


# ── _last_assistant_content ───────────────────────────────────────────────────

class TestLastAssistantContent:
    def test_returns_last_assistant(self):
        messages = [
            ChatMessage(role="user", content="질문1"),
            ChatMessage(role="assistant", content="답변1"),
            ChatMessage(role="user", content="질문2"),
            ChatMessage(role="assistant", content="답변2"),
        ]
        assert _last_assistant_content(messages) == "답변2"

    def test_returns_none_if_no_assistant(self):
        messages = [ChatMessage(role="user", content="질문1")]
        assert _last_assistant_content(messages) is None

    def test_empty_messages(self):
        assert _last_assistant_content([]) is None

    def test_last_is_user(self):
        messages = [
            ChatMessage(role="user", content="질문1"),
            ChatMessage(role="assistant", content="답변1"),
            ChatMessage(role="user", content="질문2"),
        ]
        # 마지막 user 이전의 assistant가 반환되어야 함
        assert _last_assistant_content(messages) == "답변1"


# ── 회귀 테스트: 내부 지시문 노출 패턴 ──────────────────────────────────────

class TestRegressionInstructionExposure:
    """
    실제 테스트에서 보고된 오류 케이스들:
    일반 질문이 재작성 요청으로 잘못 감지되거나,
    지시문이 포함된 텍스트가 정상 답변으로 통과되면 안 됩니다.
    """

    LOCATION_QUESTION = "자임추모공원의 위치는 어디지?"
    TIME_QUESTION = "언제부터 이런 상황이 시작됐어?"
    REWRITE_REQUEST = "한국어로 다시 말해줘"

    def test_location_question_is_not_rewrite_request(self):
        assert _is_korean_rewrite_request(self.LOCATION_QUESTION) is False

    def test_time_question_is_not_rewrite_request(self):
        assert _is_korean_rewrite_request(self.TIME_QUESTION) is False

    def test_rewrite_request_is_detected(self):
        assert _is_korean_rewrite_request(self.REWRITE_REQUEST) is True

    def test_location_question_no_cjk(self):
        # 순수 한글 질문에 CJK 없음
        assert _has_cjk(self.LOCATION_QUESTION) is False

    def test_actual_bug_response_detected_as_leak(self):
        # 실제 보고된 버그 응답이 지시문 노출로 감지되는지 확인
        bug_response = (
            "문서에서는 자임 추모공원의 정확한 위치는 어디인가요? "
            "중국어 대신 한국어로 답변해주세요."
        )
        assert _is_instruction_leak(bug_response) is True

    def test_normal_answer_passes_leak_check(self):
        # 정상 답변은 지시문 노출로 감지되면 안 됨
        normal = "자임추모공원의 위치는 문서에서 직접 언급되지 않습니다."
        assert _is_instruction_leak(normal) is False

    def test_strip_cjk_does_not_produce_instructions(self):
        # _strip_cjk 결과에 지시문이 포함되면 안 됨
        cjk_answer = "자임추모공원(紫荒追慕公园)의 위치는 문서에서 확인할 수 없습니다."
        stripped = _strip_cjk(cjk_answer)
        assert _is_instruction_leak(stripped) is False
        assert "자임추모공원" in stripped
