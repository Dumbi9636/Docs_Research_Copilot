import re
from app.clients import ollama
from app.core.config import settings
from app.schemas.summarize import SummarizeResponse


# ── 프롬프트 ──────────────────────────────────────────────────────────────────

def _single_prompt(text: str) -> str:
    return f"""당신은 문서 요약 전문가입니다.
아래 문서를 읽고 다음 규칙에 따라 한국어로 요약해 주세요.

규칙:
- 핵심 내용만 간결하게 작성합니다.
- 3~5문장으로 요약합니다.
- 불필요한 수식어나 반복 표현은 제거합니다.
- 원문에 없는 내용을 추가하지 않습니다.
- 요약문만 출력하고, 설명이나 서두는 생략합니다.

문서:
{text}

요약:"""


def _chunk_prompt(chunk: str) -> str:
    return f"""다음은 긴 문서의 일부입니다.
핵심 내용을 bullet 3개 이내로 한국어로 요약해 주세요.
설명이나 서두 없이 bullet 항목만 출력하세요.

문서 일부:
{chunk}

요약:"""


def _merge_prompt(bullet_summaries: str) -> str:
    return f"""다음은 긴 문서를 여러 부분으로 나눠 요약한 결과입니다.
이를 바탕으로 전체 문서를 3~5문장으로 통합 요약해 주세요.
중복 내용은 제거하고, 자연스러운 한 편의 요약문으로 작성하세요.
요약문만 출력하고, 설명이나 서두는 생략합니다.

부분 요약:
{bullet_summaries}

통합 요약:"""


# ── 텍스트 분할 ──────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """마침표/물음표/느낌표 뒤 공백을 기준으로 문장을 분리합니다."""
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


def _split_chunks(text: str) -> list[str]:
    """
    단락(\n\n) 기준으로 chunk를 구성합니다.
    단락이 target_chunk_size를 초과하면 문장 단위로 추가 분할합니다.
    단락 경계도 없는 경우 강제 절단을 fallback으로 사용합니다.
    """
    target = settings.target_chunk_size
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # 단락이 전혀 없으면 문장 분리로 fallback
    if not paragraphs:
        paragraphs = _split_sentences(text) or [text]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # 단락 자체가 target 초과 → 문장 단위로 쪼갬
        if len(para) > target:
            if current:
                chunks.append(current)
                current = ""
            sentences = _split_sentences(para) or [para]
            for sent in sentences:
                # 문장 하나가 target 초과 → 강제 절단
                if len(sent) > target:
                    for i in range(0, len(sent), target):
                        chunks.append(sent[i : i + target])
                elif len(current) + len(sent) > target and current:
                    chunks.append(current)
                    current = sent
                else:
                    current = (current + " " + sent).strip() if current else sent
        else:
            if len(current) + len(para) > target and current:
                chunks.append(current)
                current = para
            else:
                current = (current + "\n\n" + para).strip() if current else para

    if current:
        chunks.append(current)

    return [c for c in chunks if c]


# ── 요약 진입점 ───────────────────────────────────────────────────────────────

def summarize(text: str) -> SummarizeResponse:
    """텍스트를 받아 Ollama로 요약하고 처리 단계와 함께 반환합니다."""
    steps: list[str] = []
    steps.append("입력 검증 완료")

    if len(text) <= settings.chunk_threshold:
        return _summarize_single(text, steps)
    else:
        return _summarize_chunked(text, steps)


# ── 단일 요약 ─────────────────────────────────────────────────────────────────

def _summarize_single(text: str, steps: list[str]) -> SummarizeResponse:
    steps.append("Ollama 요청 전송")
    result = ollama.generate(_single_prompt(text))
    steps.append("응답 수신 완료")
    steps.append("요약 생성 완료")
    return SummarizeResponse(summary=result, steps=steps)


# ── 청킹 요약 ─────────────────────────────────────────────────────────────────

def _summarize_chunked(text: str, steps: list[str]) -> SummarizeResponse:
    chunks = _split_chunks(text)
    total = len(chunks)

    # chunk가 1개 이하이면 단일 요약으로 처리
    if total <= 1:
        return _summarize_single(text, steps)

    # 최대 chunk 수 초과 시 명시적 에러
    if total > settings.max_chunks:
        raise RuntimeError(
            f"문서 분할 결과 {total}개의 chunk가 생성되었습니다. "
            f"최대 허용 chunk 수({settings.max_chunks}개)를 초과했습니다. "
            f"문서를 나눠서 입력하거나 MAX_CHUNKS 설정을 조정해 주세요."
        )

    steps.append(f"문서 분할 완료 ({total}개 chunk)")

    bullet_parts: list[str] = []

    for i, chunk in enumerate(chunks, start=1):
        steps.append(f"chunk {i}/{total} 요약 중")
        try:
            result = ollama.generate(_chunk_prompt(chunk))
        except RuntimeError as e:
            steps.append(f"chunk {i}/{total} 요약 실패")
            raise RuntimeError(f"chunk {i}/{total} 요약 중 오류 발생: {e}")
        steps.append(f"chunk {i}/{total} 요약 완료")
        bullet_parts.append(result)

    steps.append("최종 통합 요약 중")
    try:
        final = ollama.generate(_merge_prompt("\n".join(bullet_parts)))
    except RuntimeError as e:
        steps.append("최종 통합 요약 실패")
        raise RuntimeError(f"최종 통합 요약 중 오류 발생: {e}")

    steps.append("최종 요약 생성 완료")
    return SummarizeResponse(summary=final, steps=steps)
