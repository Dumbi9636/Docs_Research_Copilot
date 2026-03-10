# 요약 서비스 모듈
#
# 이 모듈의 책임: 텍스트를 받아 적절한 요약 전략을 선택하고 실행합니다.
# - 짧은 문서 → 한 번의 LLM 호출로 직접 요약 (단일 요약)
# - 긴 문서   → 나눠서 각각 요약 후 통합 (청킹 요약)
#
# Ollama 호출 자체는 app/clients/ollama.py에 위임합니다.

import re
from app.clients import ollama
from app.core.config import settings
from app.schemas.summarize import SummarizeResponse


# ── 프롬프트 팩토리 ───────────────────────────────────────────────────────────
#
# 프롬프트를 별도 함수로 분리한 이유:
# 상황마다 LLM에게 기대하는 출력 형태가 다르기 때문입니다.
# - 단일 요약: "3~5문장 자연스러운 요약문" → 완성도 높은 최종 결과물
# - 청크 요약: "bullet 3개 이내" → 핵심만 압축, 머지 단계에서 재가공됩니다.
# - 머지 요약: "bullet 목록을 하나의 요약문으로" → 최종 통합 결과물

def _single_prompt(text: str) -> str:
    """
    짧은 문서용 프롬프트를 생성합니다.
    LLM이 원문 전체를 한 번에 읽고 3~5문장의 완성된 요약문을 반환하도록 유도합니다.
    """
    return f"""당신은 문서 요약 전문가입니다.
아래 문서를 읽고 다음 규칙에 따라 요약해 주세요.

[언어 규칙 — 가장 중요]
- 출력 언어는 반드시 한국어입니다.
- 입력 문서가 영어, 일본어, 중국어 등 어떤 언어로 작성되어 있더라도 요약은 반드시 한국어로만 작성합니다.
- 영어 문장으로 답하지 마세요. 단 한 문장도 영어로 출력하지 않습니다.
- 영문 고유명사나 전문 용어는 한국어 문장 안에 자연스럽게 포함시키되, 문장 자체는 한국어로 작성합니다.

[내용 규칙]
- 핵심 내용만 간결하게 작성합니다.
- 3~5문장으로 요약합니다.
- 불필요한 수식어나 반복 표현은 제거합니다.
- 원문에 없는 내용을 추가하지 않습니다.
- "요약:", "한국어 요약:", "다음은 요약입니다" 같은 머리말 없이 첫 문장부터 바로 시작합니다.
- 요약문 본문만 출력합니다. 제목, 설명, 서두, 꼬리말은 일절 쓰지 않습니다.
- 첫 문장은 주어와 서술어를 갖춘 완전한 문장으로 시작합니다. "입니다."처럼 어미만 남은 불완전한 표현으로 시작하지 않습니다.

문서:
{text}"""


def _chunk_prompt(chunk: str) -> str:
    """
    긴 문서의 각 조각(chunk)용 프롬프트를 생성합니다.

    bullet 형식을 요구하는 이유:
    - 각 chunk는 문서의 일부이므로 완결된 문장보다 핵심 포인트 추출이 목적입니다.
    - bullet은 머지 단계에서 LLM이 중복을 제거하고 통합하기 쉬운 형태입니다.
    - "서두 없이 bullet만 출력"을 명시해 불필요한 말머리를 방지합니다.
    """
    return f"""다음은 긴 문서의 일부입니다.

[언어 규칙 — 가장 중요]
- 출력 언어는 반드시 한국어입니다.
- 입력 문서가 영어 등 어떤 언어이더라도 반드시 한국어로만 출력합니다.
- 영어 문장으로 답하지 마세요.

[내용 규칙]
- 핵심 내용을 bullet 3개 이내로 요약합니다.
- 설명이나 서두 없이 bullet 항목만 출력합니다.

문서 일부:
{chunk}"""


def _merge_prompt(bullet_summaries: str) -> str:
    """
    각 chunk의 bullet 요약을 하나의 자연스러운 요약문으로 통합하는 프롬프트입니다.

    머지 단계가 필요한 이유:
    - chunk 요약들은 문서의 부분부분을 다루므로 그대로 이어붙이면 어색합니다.
    - 이 단계에서 LLM이 전체 흐름을 파악하고 중복을 제거해 완성된 요약을 만듭니다.
    - 긴 원문을 한 번에 처리하지 않고도 전체 요약 품질을 확보할 수 있습니다.
    """
    return f"""다음은 긴 문서를 여러 부분으로 나눠 요약한 결과입니다.
이를 바탕으로 전체 문서를 3~5문장으로 통합 요약해 주세요.

[언어 규칙 — 가장 중요]
- 출력 언어는 반드시 한국어입니다.
- 입력이 영어 등 어떤 언어이더라도 반드시 한국어로만 출력합니다.
- 영어 문장으로 답하지 마세요. 단 한 문장도 영어로 출력하지 않습니다.

[내용 규칙]
- 중복 내용은 제거하고, 자연스러운 한 편의 요약문으로 작성합니다.
- "요약:", "통합 요약:", "다음은 요약입니다" 같은 머리말 없이 첫 문장부터 바로 시작합니다.
- 요약문 본문만 출력합니다. 제목, 설명, 서두, 꼬리말은 일절 쓰지 않습니다.
- 첫 문장은 주어와 서술어를 갖춘 완전한 문장으로 시작합니다. "입니다."처럼 어미만 남은 불완전한 표현으로 시작하지 않습니다.

부분 요약:
{bullet_summaries}"""


# ── 후처리 ───────────────────────────────────────────────────────────────────

def _clean_summary_prefix(text: str) -> str:
    """
    LLM 응답 앞에 붙는 불필요한 머리말을 제거합니다.

    프롬프트로 금지했음에도 모델이 머리말을 출력하는 경우가 있습니다.
    이 함수는 사용자에게 최종 노출되는 summary에만 적용합니다.
    chunk 중간 bullet 결과에는 적용하지 않습니다(머지 프롬프트가 처리합니다).
    """
    # "요약:", "한국어 요약:", "요약문:", "통합 요약:" 등
    text = re.sub(r"^\s*(?:한국어\s*)?(?:통합\s*)?요약(?:문|결과)?\s*[:：]\s*", "", text)
    # "다음은 요약입니다.", "아래는 전체 요약입니다:" 등
    text = re.sub(r"^\s*(?:다음|아래)은\s+(?:\S+\s+)?요약(?:입니다|문)?[\s]*[.：:]*\s*", "", text)
    # "입니다."처럼 어미만 남은 불완전한 조각이 맨 앞에 붙는 경우를 제거합니다.
    # 정상 문장은 "입니다."로 시작하지 않으므로 오탐 위험이 낮습니다.
    text = re.sub(r"^\s*입니다\.\s*", "", text)
    return text.strip()


# ── 텍스트 분할 ──────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """마침표/물음표/느낌표 뒤 공백을 기준으로 문장을 분리합니다."""
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


def _split_chunks(text: str) -> list[str]:
    """
    텍스트를 target_chunk_size에 가깝게 분할합니다.

    분할 우선순위 (의미 단위를 최대한 보존하기 위해):
      1순위: 단락(\\n\\n) 경계 — 단락은 주제가 바뀌는 자연스러운 경계입니다.
      2순위: 문장(. ? !) 경계 — 단락이 너무 길면 문장 단위로 추가 분할합니다.
      3순위: 강제 절단 — 문장 하나가 target을 초과할 때만 사용하는 최후 수단입니다.

    강제 절단을 최후 수단으로 쓰는 이유:
    단어나 문장 중간에서 자르면 LLM이 앞뒤 맥락을 잃어 요약 품질이 떨어집니다.
    """
    target = settings.target_chunk_size
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # 단락 구분자(\n\n)가 없는 문서는 문장 단위로 fallback
    if not paragraphs:
        paragraphs = _split_sentences(text) or [text]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # 단락 자체가 target 초과 → 문장 단위로 쪼갬 (2순위)
        if len(para) > target:
            if current:
                chunks.append(current)
                current = ""
            sentences = _split_sentences(para) or [para]
            for sent in sentences:
                # 문장 하나가 target 초과 → 강제 절단 (3순위, 최후 수단)
                if len(sent) > target:
                    for i in range(0, len(sent), target):
                        chunks.append(sent[i : i + target])
                elif len(current) + len(sent) > target and current:
                    chunks.append(current)
                    current = sent
                else:
                    current = (current + " " + sent).strip() if current else sent
        else:
            # 현재 chunk에 단락을 추가하면 target 초과 → 현재 chunk 마감 (1순위)
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
    """
    텍스트를 받아 Ollama로 요약하고 처리 단계와 함께 반환합니다.

    문서 길이에 따라 전략이 분기됩니다:
    - len(text) <= chunk_threshold: 단일 요약 (_summarize_single)
    - len(text) >  chunk_threshold: 청킹 요약 (_summarize_chunked)

    steps 리스트는 요약이 어떤 단계를 거쳤는지 추적합니다.
    프론트엔드에서 진행 상황을 표시하거나, 디버깅 시 흐름을 파악하는 데 씁니다.
    """
    steps: list[str] = []
    steps.append("입력 검증 완료")

    if len(text) <= settings.chunk_threshold:
        return _summarize_single(text, steps)
    else:
        return _summarize_chunked(text, steps)


# ── 단일 요약 ─────────────────────────────────────────────────────────────────

def _summarize_single(text: str, steps: list[str]) -> SummarizeResponse:
    """
    짧은 문서를 한 번의 LLM 호출로 요약합니다.

    청킹 요약 도중 chunk가 1개만 생성됐을 때도 이 함수로 fallback합니다.
    (1개짜리 chunk를 bullet으로 요약하고 머지하는 건 불필요한 LLM 호출입니다)
    """
    steps.append("Ollama 요청 전송")
    result = _clean_summary_prefix(ollama.generate(_single_prompt(text)))
    steps.append("응답 수신 완료")
    steps.append("요약 생성 완료")
    return SummarizeResponse(summary=result, steps=steps)


# ── 청킹 요약 ─────────────────────────────────────────────────────────────────

def _summarize_chunked(text: str, steps: list[str]) -> SummarizeResponse:
    """
    긴 문서를 여러 chunk로 나눠 요약하고, 결과를 통합합니다.

    왜 긴 문서를 한 번에 요약하지 않는가:
    - LLM은 처리할 수 있는 토큰(컨텍스트) 한계가 있습니다.
    - 한계를 초과하면 응답이 잘리거나 중요한 내용이 누락됩니다.
    - chunk 단위로 나눠 처리하면 어떤 길이의 문서도 안정적으로 다룰 수 있습니다.

    흐름: 분할 → 각 chunk bullet 요약 → 전체 통합 요약
    """
    chunks = _split_chunks(text)
    total = len(chunks)

    # chunk가 1개 이하면 단일 요약으로 처리합니다.
    # 이유: 1개짜리를 bullet 요약 후 머지하면 LLM을 2번 호출하는 낭비가 됩니다.
    if total <= 1:
        return _summarize_single(text, steps)

    # 최대 chunk 수 초과 시 조용히 누락하지 않고 명시적 에러를 냅니다.
    # 이유: 누락되면 사용자가 요약이 불완전한지 알 방법이 없습니다.
    #       에러를 내서 "문서를 나눠 입력하거나 MAX_CHUNKS를 조정하라"고 안내합니다.
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
            # 실패한 chunk 번호를 steps와 에러 메시지에 모두 남깁니다.
            # 이유: "어디서 실패했는가"를 알아야 디버깅이 가능합니다.
            #       단순히 "요약 실패"만 남기면 10개 chunk 중 어느 것인지 모릅니다.
            steps.append(f"chunk {i}/{total} 요약 실패")
            raise RuntimeError(f"chunk {i}/{total} 요약 중 오류 발생: {e}")
        steps.append(f"chunk {i}/{total} 요약 완료")
        bullet_parts.append(result)

    # 모든 chunk의 bullet 요약을 하나로 이어붙여 머지 프롬프트에 전달합니다.
    steps.append("최종 통합 요약 중")
    try:
        final = _clean_summary_prefix(ollama.generate(_merge_prompt("\n".join(bullet_parts))))
    except RuntimeError as e:
        steps.append("최종 통합 요약 실패")
        raise RuntimeError(f"최종 통합 요약 중 오류 발생: {e}")

    steps.append("최종 요약 생성 완료")
    return SummarizeResponse(summary=final, steps=steps)
