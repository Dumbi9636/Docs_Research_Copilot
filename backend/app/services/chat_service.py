# 문서 기반 대화 서비스
#
# 이 모듈의 책임:
# - 원문(input_text)과 요약문(output_summary)을 조합해 최적의 컨텍스트를 구성합니다.
# - 컨텍스트 + 이전 대화 + 새 질문을 합쳐 프롬프트를 조립합니다.
# - Ollama generate를 호출해 답변을 반환합니다.
#
# 컨텍스트 선택 전략 (input_text 길이 기준):
#   None 또는 < MIN_INPUT_QUALITY  → 요약문만 사용 (fallback)
#   ≤ FULL_TEXT_THRESHOLD (6000자) → 원문 전체 + 요약문
#   > FULL_TEXT_THRESHOLD          → 요약문 + 키워드 기반 관련 문단 선택
#
# Phase 2 확장 포인트:
#   _select_relevant_paragraphs() 함수를 임베딩 기반 유사도 검색으로 교체하면
#   chat_service 외부 코드 변경 없이 벡터 검색으로 전환할 수 있습니다.

import logging
import re

from app.clients import ollama
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

# ── 상수 ──────────────────────────────────────────────────────────────────────

# 이전 대화 중 프롬프트에 포함할 최대 메시지 수 (Q&A 3턴 = 6개)
MAX_HISTORY_TURNS = 6

# 이 길이(자) 이상인 원문은 전체를 컨텍스트에 포함합니다.
# 이보다 길면 관련 문단 선택 방식으로 전환합니다.
FULL_TEXT_THRESHOLD = 6000

# 원문이 이 길이(자) 미만이면 OCR 노이즈 등 비정상 텍스트로 판단해 fallback합니다.
MIN_INPUT_QUALITY = 50

# 관련 문단 선택 시 포함할 최대 총 글자 수
RELEVANT_MAX_CHARS = 3000

# ── 언어 감지 · 재정리 관련 상수 ─────────────────────────────────────────────

# CJK Unified Ideographs + Extension A (중국어·일본어 한자)
# 한글(AC00-D7A3, 1100-11FF)은 이 범위에 포함되지 않으므로 안전합니다.
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# "한국어로 다시 말해줘" 류의 언어 재정리 요청 감지용 키워드
_KO_LANG_TRIGGERS: frozenset[str] = frozenset({
    "한국어로", "한글로", "한국어만", "한글만",
})
_KO_REWRITE_ACTIONS: frozenset[str] = frozenset({
    "다시", "바꿔", "써줘", "말해줘", "작성해줘", "정리해줘", "번역해줘", "고쳐줘",
})

# 재작성 결과에서 내부 지시문이 노출된 경우를 감지합니다.
# "해주세요", "중국어 대신", "답변해 주" 등이 있으면 모델이 지시문을 출력한 것으로 판단합니다.
_INSTRUCTION_LEAK_RE = re.compile(
    r"(해\s*주\s*세\s*요|답변해\s*주|작성해\s*주|중국어\s*대신|한국어로\s*답변)"
)

# ── 불용어 목록 ──────────────────────────────────────────────────────────────
# 키워드 추출 시 의미 없는 조사/어미/질문어/요청어를 제외합니다.
# 필요에 따라 항목을 추가하면 됩니다.
_STOPWORDS: frozenset[str] = frozenset({
    # 조사
    "이", "가", "을", "를", "의", "에", "과", "와", "은", "는", "도",
    "로", "으로", "에서", "에게", "부터", "까지", "만", "하고", "이랑",
    # 의문사
    "뭐", "뭔", "무엇", "어떤", "어떻게", "왜", "언제", "어디", "누가", "누구",
    # 요청어
    "해줘", "알려줘", "설명해줘", "말해줘", "찾아줘", "보여줘", "정리해줘",
    # 일반 연결어·대명사
    "있어", "없어", "이야", "인가", "인지", "것", "거", "좀", "다시",
    "그냥", "그리고", "그러면", "그래서", "하지만", "그런데", "또한",
    "만약", "만일", "혹시", "바로", "모두", "전체", "전부", "특히",
})


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _has_cjk(text: str) -> bool:
    """CJK(중국어·일본어) 문자가 포함되어 있으면 True를 반환합니다."""
    return bool(_CJK_RE.search(text))


def _strip_cjk(text: str) -> str:
    """
    CJK 문자를 제거하고 주변 공백을 정리합니다.
    Ollama를 호출하지 않으므로 오작동 위험이 없습니다.

    자동 후처리(CJK 감지 시)에만 사용합니다.
    사용자 명시 요청("한국어로 다시 말해줘")에는 _rewrite_korean_ollama()를 사용합니다.
    """
    cleaned = _CJK_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)   # 연속 공백 정리
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)    # 3줄 이상 빈 줄 → 2줄
    return cleaned.strip()


def _is_instruction_leak(text: str) -> bool:
    """
    텍스트에 내부 지시문이 노출되었는지 감지합니다.

    "해주세요", "중국어 대신", "한국어로 답변" 등의 패턴이 있으면
    모델이 답변 대신 지시문을 출력한 것으로 판단합니다.
    """
    return bool(_INSTRUCTION_LEAK_RE.search(text))


def _is_korean_rewrite_request(question: str) -> bool:
    """
    '한국어로 다시 말해줘' 류의 언어 재정리 요청인지 판별합니다.

    한국어 언어 트리거(_KO_LANG_TRIGGERS)와 재작성 동작어(_KO_REWRITE_ACTIONS)가
    모두 포함되어 있을 때만 True를 반환합니다.
    """
    q = question.strip()
    return (
        any(t in q for t in _KO_LANG_TRIGGERS)
        and any(a in q for a in _KO_REWRITE_ACTIONS)
    )


def _last_assistant_content(messages: list[ChatMessage]) -> str | None:
    """이전 대화에서 마지막 assistant 메시지의 내용을 반환합니다. 없으면 None."""
    for msg in reversed(messages):
        if msg.role == "assistant":
            return msg.content
    return None


def _rewrite_korean(text: str) -> str:
    """
    사용자가 명시적으로 요청한 경우에만 한국어 재정리를 수행합니다.
    ("한국어로 다시 말해줘" 전용 — 자동 후처리에는 사용하지 않습니다.)

    프롬프트 설계 원칙:
    - Ollama는 /api/generate(completion API)를 사용합니다.
    - 프롬프트 끝에 "[한국어 재작성]" 같은 태그를 두면 소형 모델이
      태그를 "이어 쓸 문장의 종류"로 읽어 지시문을 출력하는 오류가 발생합니다.
    - 대신 지시 + 원본 텍스트를 앞에 두고, 모델이 텍스트를 그대로 이어 쓰도록 유도합니다.

    Ollama 결과 검증:
    - 지시문 노출(_is_instruction_leak) → _strip_cjk() fallback
    - 너무 짧은 결과(< 10자) → _strip_cjk() fallback
    - Ollama 호출 실패 → _strip_cjk() fallback
    """
    # Completion-friendly 프롬프트:
    # 지시를 맨 앞에 두고, 원본 텍스트를 바로 이어 붙입니다.
    # 모델은 원본 텍스트를 "계속 쓸 내용"으로 인식해 한국어로 완성합니다.
    prompt = (
        "다음 텍스트의 중국어·한자를 자연스러운 한국어로 바꿔서 출력하라."
        " 설명이나 머리말 없이 변환된 텍스트만 출력한다.\n\n"
        f"{text}"
    )
    logger.debug(
        "[chat_service] _rewrite_korean 호출 | 입력 길이=%d chars | CJK=%s",
        len(text), _has_cjk(text),
    )
    try:
        result = ollama.generate(prompt, num_predict=max(512, len(text) + 100))
        leak = _is_instruction_leak(result)
        too_short = len(result.strip()) < 10
        logger.debug(
            "[chat_service] _rewrite_korean 결과 | 출력 길이=%d | 지시문노출=%s | 너무짧음=%s",
            len(result), leak, too_short,
        )
        if leak or too_short:
            logger.warning("[chat_service] _rewrite_korean 비정상 결과 → _strip_cjk fallback")
            return _strip_cjk(text)
        return result
    except Exception as exc:
        logger.warning("[chat_service] _rewrite_korean Ollama 오류 → _strip_cjk fallback: %s", exc)
        return _strip_cjk(text)


def _extract_keywords(question: str) -> frozenset[str]:
    """
    질문에서 의미 있는 키워드를 추출합니다.

    기준:
    - 공백으로 단어 분리
    - 길이 2자 이하 제외 (조사·어미가 대부분)
    - 불용어 목록에 있는 단어 제외
    """
    return frozenset(
        w for w in question.split()
        if len(w) > 2 and w not in _STOPWORDS
    )


def _select_relevant_paragraphs(
    text: str,
    question: str,
    max_chars: int = RELEVANT_MAX_CHARS,
) -> str:
    """
    질문과 관련성이 높은 문단을 원문에서 선택합니다.

    알고리즘:
    1. 질문에서 키워드 추출 (불용어·단문자 제외)
    2. 원문을 문단 단위로 분리 (빈 줄 → 줄바꿈 순으로 시도)
    3. 각 문단에 키워드 겹침 점수 부여
    4. 점수 높은 순으로 선택 (max_chars 이내)
    5. 원문 순서 복원 후 반환

    Phase 2 교체 포인트:
    - 이 함수를 임베딩 코사인 유사도 기반 검색으로 교체하면
      외부 호출부 변경 없이 벡터 검색으로 전환됩니다.
    """
    keywords = _extract_keywords(question)

    # 문단 분리: 빈 줄 → 단순 줄바꿈 순으로 시도
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # 문단이 없거나 키워드가 없으면 앞부분만 반환
    if not paragraphs:
        return text[:max_chars]
    if not keywords:
        return text[:max_chars]

    # 각 문단에 점수 부여 (인덱스를 보존해 원문 순서 복원에 사용)
    scored: list[tuple[int, int, str]] = []  # (score, original_idx, paragraph)
    for idx, paragraph in enumerate(paragraphs):
        score = sum(1 for kw in keywords if kw in paragraph)
        scored.append((score, idx, paragraph))

    # 점수 내림차순 정렬 (동점이면 앞 문단 우선)
    scored.sort(key=lambda x: (-x[0], x[1]))

    # 상위 문단을 max_chars 이내로 그리디 선택
    selected: list[tuple[int, str]] = []  # (original_idx, paragraph)
    total_chars = 0
    for score, idx, paragraph in scored:
        if total_chars + len(paragraph) > max_chars:
            continue  # 이 문단이 너무 길면 건너뛰고 다음 후보 검토
        selected.append((idx, paragraph))
        total_chars += len(paragraph)

    # 아무것도 선택되지 않았으면 가장 높은 점수 문단만 잘라서 반환
    if not selected:
        _, _, best_paragraph = scored[0]
        return best_paragraph[:max_chars]

    # 원문 순서로 재정렬 후 반환
    selected.sort(key=lambda x: x[0])
    return "\n\n".join(p for _, p in selected)


def _build_context(
    summary: str,
    input_text: str | None,
    question: str,
) -> tuple[str, str]:
    """
    답변에 사용할 컨텍스트 블록을 구성합니다.

    Returns:
        (context_block, source_label)
        context_block: 프롬프트에 삽입할 문서 컨텍스트 텍스트
        source_label:  프롬프트 안내 문구용 ("원문 전체", "원문 관련 구절", "문서 요약")

    Phase 2 확장:
        이 함수에서 _select_relevant_paragraphs()를 호출하는 대신
        임베딩 기반 검색 함수를 호출하도록 교체하면 됩니다.
    """
    # ── fallback 1: input_text 없음 (이 컬럼 추가 전 생성된 구버전 기록) ──────
    if not input_text:
        return f"[문서 요약]\n{summary}", "문서 요약"

    # ── fallback 2: 비정상적으로 짧은 텍스트 (OCR 노이즈, 빈 파일 등) ─────────
    cleaned = input_text.strip()
    if len(cleaned) < MIN_INPUT_QUALITY:
        return f"[문서 요약]\n{summary}", "문서 요약"

    # ── 단문서: 원문 전체 포함 (원문 → 요약 순서: 원문이 검증 기준) ──────────
    if len(cleaned) <= FULL_TEXT_THRESHOLD:
        context = f"[원문 — 검증 기준]\n{cleaned}\n\n[요약 — 참고용]\n{summary}"
        return context, "원문 전체"

    # ── 장문서: 관련 문단 선택 (원문 구절 → 요약 순서로 원문 우선) ──────────
    relevant = _select_relevant_paragraphs(cleaned, question)
    context = f"[원문 관련 구절 — 검증 기준]\n{relevant}\n\n[요약 — 참고용]\n{summary}"
    return context, "원문 관련 구절"


def _build_prompt(
    context_block: str,
    source_label: str,
    messages: list[ChatMessage],
    question: str,
    mode: str = "chat",
) -> str:
    """
    최종 Ollama 프롬프트를 조립합니다.

    mode:
      strict — 문서에 있는 내용만 답변. 없으면 "문서에서 확인할 수 없습니다."
      chat   — 문서 근거 우선, 부족하면 해석·일반 설명 허용 (층위 표시 필수)

    구조:
    1. 시스템 역할 + 규칙 (source_label, mode 포함)
    2. 문서 컨텍스트 (context_block)
    3. 이전 대화 (최근 MAX_HISTORY_TURNS개 슬라이딩 윈도우)
    4. 새 질문
    """
    # 이전 대화 블록 (없으면 생략)
    conversation_block = ""
    if messages:
        recent = messages[-MAX_HISTORY_TURNS:]
        lines = []
        for msg in recent:
            label = "사용자" if msg.role == "user" else "AI"
            lines.append(f"{label}: {msg.content}")
        conversation_block = "\n[이전 대화]\n" + "\n".join(lines) + "\n"

    if mode == "strict":
        system_rules = f"""당신은 문서 분석 전문가입니다.
아래 제공된 {source_label}만을 근거로 사용자 질문에 답변하세요.
"원문 — 검증 기준" 섹션이 있으면 이것을 가장 우선합니다. "요약 — 참고용"은 보조로만 씁니다.

[전제 검증 — 답변 전 필수]
질문에 포함된 전제나 주장이 문서에서 실제로 확인되는지 먼저 점검하세요.
- 전제가 문서와 다르거나 과장되어 있으면, 그 전제를 교정하고 문서 기준의 사실을 답합니다.
- 예: 문서에 '공격 위협'만 있는데 "왜 공격했지?"라고 물으면
  → "문서에서는 실제 공격이 아니라 공격 위협/준비 단계로 기술되어 있습니다."라고 교정합니다.

[답변 규칙]
- 문서에 있는 내용만 답변합니다.
- 문서에 없는 내용은 반드시 "문서에는 해당 내용이 언급되지 않습니다."를 먼저 밝힙니다.
- 추측하거나 일반 지식으로 보완하지 않습니다.
- 출력 언어는 반드시 한국어입니다. 중국어(한자)·일본어를 단 한 글자도 출력하지 않습니다.
- 답변은 명확하고 간결하게 작성합니다. 필요한 경우 bullet 형식을 사용해도 됩니다.
- 답변 앞에 "AI:", "답변:", "다음과 같습니다" 같은 머리말을 붙이지 않습니다.
- 첫 문장부터 바로 답변 내용을 시작합니다."""
    else:  # chat mode (default)
        system_rules = f"""당신은 문서 기반 대화 전문가입니다.
아래 제공된 {source_label}을 참고해 사용자 질문에 자연스럽게 답변하세요.
"원문 — 검증 기준" 섹션이 있으면 이것을 가장 우선합니다. "요약 — 참고용"은 보조로만 씁니다.

[전제 검증 — 답변 전 필수]
질문에 포함된 전제나 주장이 문서에서 실제로 확인되는지 먼저 점검하세요.
- 전제가 문서와 다르거나 과장되어 있으면, 그 전제를 먼저 교정한 뒤 답변합니다.
- 예: 문서에 '공격 위협'만 있는데 "왜 공격했지?"라고 물으면
  → "문서에서는 실제 공격이 아니라 공격 위협/준비 단계로 기술되어 있습니다. 그 배경으로는..."처럼 교정 후 답변합니다.

[답변 3층위 — 반드시 구분해서 표현할 것]
① 문서에서 직접 확인된 사실
   → 수식어 없이 그대로 서술합니다.

② 문서 내용을 바탕으로 한 추론/해석
   → "문서를 바탕으로 해석하면", "정황상", "문서에서 추론하면" 같은 표현을 앞에 붙입니다.

③ 문서에 없는 일반 배경지식 (최소한으로만 허용)
   → 반드시 "문서에는 구체적인 내용이 언급되지 않습니다"를 먼저 밝힙니다.
   → 그 뒤에 "일반적으로는"으로 시작하는 1~2문장 이내로만 보충합니다.
   → 일반론을 길게 나열하거나 상세히 확장하지 않습니다.
   → 이 내용을 사실처럼 단정하지 않습니다.

[추가 금지 사항]
- 문서에 없는 내용을 사실처럼 단정하지 않습니다.
- 문서와 전혀 무관한 질문에는 이 시스템이 문서 기반임을 안내하고 정중히 거절합니다.
- 출력 언어는 반드시 한국어입니다. 중국어(한자)·일본어를 단 한 글자도 출력하지 않습니다.
- 답변 앞에 "AI:", "답변:", "다음과 같습니다" 같은 머리말을 붙이지 않습니다.
- 첫 문장부터 바로 답변 내용을 시작합니다."""

    return f"""{system_rules}

{context_block}
{conversation_block}
[새 질문]
사용자: {question}

AI:"""


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def answer(
    summary: str,
    input_text: str | None,
    messages: list[ChatMessage],
    question: str,
    mode: str = "chat",
) -> str:
    """
    문서를 기반으로 질문에 답변합니다.

    Args:
        summary:    SUMMARY_HISTORY.output_summary (요약문)
        input_text: SUMMARY_HISTORY.input_text (원문 텍스트, 구버전 기록은 None)
        messages:   이전 대화 목록 (첫 질문이면 빈 리스트)
        question:   사용자의 새 질문
        mode:       "strict" (문서 근거만) | "chat" (해석·일반 설명 허용, 기본값)

    Returns:
        LLM이 생성한 답변 문자열

    Raises:
        RuntimeError: Ollama 연결 실패, 타임아웃, 빈 응답 등
    """
    # ── 특수 케이스: "한국어로 다시 말해줘" 요청 ────────────────────────────────
    # 일반 Q&A 흐름을 거치지 않고 이전 답변을 직접 재정리합니다.
    # _rewrite_korean()은 이 경로에서만 Ollama를 호출합니다.
    if _is_korean_rewrite_request(question):
        logger.debug("[chat_service] 한국어 재작성 요청 감지 | question=%r", question[:80])
        prev = _last_assistant_content(messages)
        if prev:
            return _rewrite_korean(prev)
        return "다시 정리할 이전 답변이 없습니다. 먼저 질문을 입력해 주세요."

    # ── 일반 Q&A 흐름 ────────────────────────────────────────────────────────
    context_block, source_label = _build_context(summary, input_text, question)
    prompt = _build_prompt(context_block, source_label, messages, question, mode)
    # chat 모드는 해석·설명이 추가되므로 토큰을 더 허용합니다.
    num_predict = 512 if mode == "strict" else 768
    result = ollama.generate(prompt, num_predict=num_predict)

    logger.debug(
        "[chat_service] 원본 모델 응답 | 길이=%d | CJK포함=%s | 앞100자=%r",
        len(result), _has_cjk(result), result[:100],
    )

    # ── 후처리: CJK 감지 → regex 제거 (Ollama 재호출 없음) ───────────────────
    # 주의: 여기서는 _rewrite_korean()을 사용하지 않습니다.
    # 소형 completion 모델이 재작성 지시문 자체를 출력하는 오류를 방지하기 위해
    # 순수 regex(_strip_cjk)로만 처리합니다.
    if _has_cjk(result):
        stripped = _strip_cjk(result)
        logger.debug(
            "[chat_service] CJK strip 적용 | 전=%d chars → 후=%d chars | 결과앞100자=%r",
            len(result), len(stripped), stripped[:100],
        )
        result = stripped

    return result
