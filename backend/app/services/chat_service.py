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

from app.clients import ollama
from app.schemas.chat import ChatMessage

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

    # ── 단문서: 원문 전체 포함 ───────────────────────────────────────────────
    if len(cleaned) <= FULL_TEXT_THRESHOLD:
        context = f"[원문]\n{cleaned}\n\n[요약]\n{summary}"
        return context, "원문 전체"

    # ── 장문서: 관련 문단 선택 ──────────────────────────────────────────────
    relevant = _select_relevant_paragraphs(cleaned, question)
    context = f"[요약]\n{summary}\n\n[원문 중 관련 구절]\n{relevant}"
    return context, "원문 관련 구절"


def _build_prompt(
    context_block: str,
    source_label: str,
    messages: list[ChatMessage],
    question: str,
) -> str:
    """
    최종 Ollama 프롬프트를 조립합니다.

    구조:
    1. 시스템 역할 + 규칙 (source_label 포함)
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

    return f"""당신은 문서 분석 전문가입니다.
아래 제공된 {source_label}을 기반으로 사용자 질문에 답변하세요.

[중요 규칙]
- 반드시 아래 제공된 문서 내용만 기반으로 답변합니다.
- 제공된 내용에 없는 정보는 추측하거나 보완하지 않고, "문서에서 확인할 수 없습니다."라고 답합니다.
- 출력 언어는 반드시 한국어입니다. 어떤 경우에도 한국어 이외의 언어로 답하지 않습니다.
- 중국어(한자)·일본어를 출력하지 않습니다.
- 답변은 명확하고 간결하게 작성합니다. 필요한 경우 bullet 형식을 사용해도 됩니다.
- 답변 앞에 "AI:", "답변:", "다음과 같습니다" 같은 머리말을 붙이지 않습니다.
- 첫 문장부터 바로 답변 내용을 시작합니다.

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
) -> str:
    """
    문서를 기반으로 질문에 답변합니다.

    Args:
        summary:    SUMMARY_HISTORY.output_summary (요약문)
        input_text: SUMMARY_HISTORY.input_text (원문 텍스트, 구버전 기록은 None)
        messages:   이전 대화 목록 (첫 질문이면 빈 리스트)
        question:   사용자의 새 질문

    Returns:
        LLM이 생성한 답변 문자열

    Raises:
        RuntimeError: Ollama 연결 실패, 타임아웃, 빈 응답 등
    """
    context_block, source_label = _build_context(summary, input_text, question)
    prompt = _build_prompt(context_block, source_label, messages, question)
    return ollama.generate(prompt, num_predict=512)
