# 문서 기반 대화 서비스
#
# 이 모듈의 책임:
# - 문서 요약 + 이전 대화 + 새 질문을 합쳐 프롬프트를 조립합니다.
# - Ollama generate를 호출해 답변을 반환합니다.
#
# 대화 길이 제한:
# - 이전 대화가 길어질수록 프롬프트 토큰이 증가합니다.
# - MAX_HISTORY_TURNS(최근 N개 메시지)만 프롬프트에 포함해 토큰 폭증을 방지합니다.

from app.clients import ollama
from app.schemas.chat import ChatMessage

# 프롬프트에 포함할 이전 대화 메시지 최대 개수 (Q&A 각 1개씩 → 3턴 = 6개)
# Phase 2에서 슬라이딩 윈도우 크기를 설정값으로 분리할 수 있습니다.
MAX_HISTORY_TURNS = 6


def _build_prompt(summary: str, messages: list[ChatMessage], question: str) -> str:
    """
    프롬프트 조립 함수.

    구조:
    1. 시스템 역할 + 규칙 선언
    2. 문서 요약 (항상 포함)
    3. 이전 대화 (최근 MAX_HISTORY_TURNS개만 포함, 없으면 블록 생략)
    4. 새 질문

    확장 시 고려사항:
    - 문서 원문이 DB에 저장되면 요약문 대신 원문을 넣을 수 있습니다.
    - 슬라이딩 윈도우 크기를 settings로 옮기면 config에서 조절 가능합니다.
    """
    # 슬라이딩 윈도우: 최근 메시지만 포함
    recent = messages[-MAX_HISTORY_TURNS:] if len(messages) > MAX_HISTORY_TURNS else messages

    # 이전 대화 블록 조립 (메시지가 없으면 블록 자체를 생략)
    conversation_block = ""
    if recent:
        lines = []
        for msg in recent:
            label = "사용자" if msg.role == "user" else "AI"
            lines.append(f"{label}: {msg.content}")
        conversation_block = "\n[이전 대화]\n" + "\n".join(lines) + "\n"

    return f"""당신은 문서 분석 전문가입니다.
아래 제공된 문서 요약을 기반으로 사용자 질문에 답변하세요.

[중요 규칙]
- 반드시 아래 [문서 요약] 내용만 기반으로 답변합니다.
- 문서 요약에 언급되지 않은 내용은 추측하거나 보완하지 않고, "문서에서 확인할 수 없습니다."라고 답합니다.
- 출력 언어는 반드시 한국어입니다. 어떤 경우에도 한국어 이외의 언어로 답하지 않습니다.
- 답변은 명확하고 간결하게 작성합니다. 필요한 경우 bullet 형식을 사용해도 됩니다.
- 답변 앞에 "AI:", "답변:", "다음과 같습니다" 같은 머리말을 붙이지 않습니다.
- 첫 문장부터 바로 답변 내용을 시작합니다.

[문서 요약]
{summary}
{conversation_block}
[새 질문]
사용자: {question}

AI:"""


def answer(summary: str, messages: list[ChatMessage], question: str) -> str:
    """
    문서 요약을 컨텍스트로 삼아 질문에 답변합니다.

    Args:
        summary:  SUMMARY_HISTORY.output_summary (문서 요약문)
        messages: 이전 대화 목록 (첫 질문이면 빈 리스트)
        question: 사용자의 새 질문

    Returns:
        LLM이 생성한 답변 문자열

    Raises:
        RuntimeError: Ollama 연결 실패, 타임아웃, 빈 응답 등
    """
    prompt = _build_prompt(summary, messages, question)
    # 대화형 답변은 요약보다 짧아도 되므로 num_predict를 512로 제한합니다.
    return ollama.generate(prompt, num_predict=512)
