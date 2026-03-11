# 요약 서비스 모듈
#
# 이 모듈의 책임: 텍스트를 받아 적절한 요약 전략을 선택하고 실행합니다.
# - 짧은 문서 → 한 번의 LLM 호출로 직접 요약 (단일 요약)
# - 긴 문서   → 나눠서 각각 요약 후 통합 (청킹 요약)
#
# Ollama 호출 자체는 app/clients/ollama.py에 위임합니다.

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
- 중국어(한자) 문장을 출력하지 않습니다. 단 한 글자도 중국어로 쓰지 않습니다.
- 영어 문장으로 답하지 마세요. 단 한 문장도 영어로 출력하지 않습니다.
- 영문 고유명사나 전문 용어(AI, CPU 등)는 한국어 문장 안에 자연스럽게 포함시키되, 문장 자체는 한국어로 작성합니다.
- "계속 중국어로", "继续用中文", "若要概括", "请用韩语" 같은 언어 전환·지시 문구를 출력하지 않습니다.
- 첫 번째 글자부터 한국어 문장으로 시작합니다. 요약 방법을 안내하거나 설명하는 문장을 앞에 붙이지 않습니다.

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
    # chunk 프롬프트는 중간 단계용이므로 언어 규칙을 간결하게 유지합니다.
    # 최종 언어 품질은 merge 단계의 강화된 규칙에서 보장합니다.
    # 프롬프트를 짧게 유지할수록 chunk 호출당 처리 시간이 줄어듭니다.
    #
    # 중국어 금지를 명시하는 이유:
    # qwen 계열은 중국어가 내부 처리 언어여서, 한국어 지시를 받아도 중국어로 drift하는 경향이 있습니다.
    # "한국어로만"이라는 긍정 지시보다 "중국어 금지"라는 부정 지시를 함께 쓰는 것이 더 효과적입니다.
    return f"""다음은 긴 문서의 일부입니다.

출력 언어: 반드시 한국어만 사용합니다. 중국어(한자)·영어·일본어로 출력하지 않습니다.

핵심 내용을 bullet 3개 이내로 요약합니다.
설명이나 서두 없이 bullet 항목만 출력합니다.

문서 일부:
{chunk}"""


def _merge_prompt(bullet_summaries: str, target_sentences: str) -> str:
    """
    각 chunk의 bullet 요약을 하나의 자연스러운 요약문으로 통합하는 프롬프트입니다.

    target_sentences: "3~5", "5~7", "7~9", "9~11" 등 chunk 수에 따라 결정됩니다.
    chunk 중간 요약은 짧게 유지하고 이 단계에서만 출력 길이를 조정합니다.

    머지 단계가 필요한 이유:
    - chunk 요약들은 문서의 부분부분을 다루므로 그대로 이어붙이면 어색합니다.
    - 이 단계에서 LLM이 전체 흐름을 파악하고 중복을 제거해 완성된 요약을 만듭니다.
    - 긴 원문을 한 번에 처리하지 않고도 전체 요약 품질을 확보할 수 있습니다.
    """
    # "~해 주세요" 요청형 대신 "~작성합니다" 서술형을 씁니다.
    # 요청형은 모델이 작업을 수락하는 메타 문장("여기 N문장으로 요약해 드리겠습니다")을
    # 먼저 출력하도록 유도하기 때문입니다.
    return f"""다음은 긴 문서를 여러 부분으로 나눠 요약한 결과입니다.
아래 부분 요약들을 바탕으로 {target_sentences}문장의 통합 요약문을 작성합니다.

[언어 규칙 — 가장 중요]
- 출력 언어는 반드시 한국어입니다.
- 입력 부분 요약이 영어, 중국어, 일본어 등 어떤 언어이더라도 반드시 한국어로만 출력합니다.
- 중국어(한자) 문장을 출력하지 않습니다. 단 한 글자도 중국어로 쓰지 않습니다.
- 영어 문장으로 답하지 않습니다. 단 한 문장도 영어로 출력하지 않습니다.
- "계속 중국어로", "继续用中文" 같은 언어 전환 지시문을 출력하지 않습니다.

[내용 규칙]
- 중복 내용은 제거하고, 자연스러운 한 편의 요약문으로 작성합니다.
- 요약문 본문만 출력합니다. 제목, 설명, 서두, 꼬리말은 일절 쓰지 않습니다.
- 몇 문장을 쓸 것인지, 요약을 시작한다는 안내 문장은 쓰지 않습니다.
- "요약:", "통합 요약:", "다음과 같이 요약합니다" 같은 머리말 없이 첫 문장부터 바로 시작합니다.
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
    # "5~7문장으로 요약해 드리겠습니다." 처럼 목표 문장 수를 언급하는 메타 안내문을 제거합니다.
    # 정상 요약 본문은 "숫자~숫자문장"으로 시작하지 않으므로 오탐 위험이 낮습니다.
    text = re.sub(r"^\s*[^\n.]*\d+[~\-]\d+\s*문장[^\n.]*\.\s*", "", text)
    # "다음과 같이 요약합니다/드리겠습니다" 류의 메타 안내문을 제거합니다.
    # "합니다/하겠습니다/드리겠습니다"로 끝나는 경우만 제거해 오탐을 최소화합니다.
    text = re.sub(r"^\s*다음과\s+같이?\s+[^\n]*(?:요약|정리)(?:합니다|하겠습니다|드리겠습니다)[^\n]*\.\s*", "", text)
    # 중국어 지시문이 콜론(：/:)으로 끝나며 접두어로 붙는 패턴을 제거합니다.
    # 예: "若要概括这段内容，请用韩语简要总结：이 문서는..." → "이 문서는..."
    #
    # 제거 조건:
    # - 텍스트 시작부터 첫 콜론까지 CJK 문자(U+4E00-U+9FFF)·CJK 구두점·공백만 있어야 합니다.
    # - 한글(U+AC00-U+D7A3)이 콜론 이전에 있으면 매칭하지 않아 한국어 문장은 보존됩니다.
    # - 콜론 이후 내용(실제 한국어 요약)은 그대로 유지됩니다.
    text = re.sub(r"^\s*[\u4e00-\u9fff，。！？、\s]+[：:]\s*", "", text)
    return text.strip()


def _strip_language_noise(text: str) -> str:
    """
    중국어 오염 문장과 언어 메타 지시문을 제거합니다.

    _clean_summary_prefix가 앞머리 패턴만 다루는 것과 달리,
    이 함수는 본문 중간에 섞인 오염 라인을 줄 단위로 정리합니다.

    적용 대상:
    - 사용자에게 최종 노출되는 summary (single / merge 모두)

    설계 원칙:
    - 오탐(정상 한국어 문장 제거) 위험을 최소화하기 위해 보수적 기준을 사용합니다.
    - 한자가 4자 이상이고 해당 줄에서 CJK 문자 중 한자 비율이 80% 이상인 줄만 제거합니다.
    - 현대 한국어에는 한자(Hanja)가 거의 없으므로 오탐 위험이 낮습니다.
    """
    # ── 1단계: 알려진 중국어 메타 지시문 패턴을 줄째로 제거 ─────────────────────
    # 실제 관측된 패턴들:
    #   "继续用中文完成总结"   → "중국어로 계속 요약을 완성합니다"
    #   "应当继续用中文完成总结" → "중국어로 계속 완성해야 합니다"
    # [^\n]* 로 해당 줄 전체를 매칭해 줄 단위로 제거합니다.
    known_patterns = [
        r"[^\n]*继续用中文[^\n]*",           # "계속 중국어로" 변형 전체
        r"[^\n]*应当继续用中文[^\n]*",       # "중국어로 계속해야" 변형 전체
        r"[^\n]*中文摘要[^\n]*",             # "중국어 요약" 표제
        r"[^\n]*用中文(?:完成|作答|输出)[^\n]*",  # "중국어로 완성/답변/출력"
        # qwen 특이 패턴: 작업 수락 표현을 중국어로 내보내는 경우
        r"[^\n]*好的[，,]\s*以下是[^\n]*",        # "好的，以下是韩语摘要：" 류
        r"[^\n]*以下是(?:总结|摘要|韩语)[^\n]*",  # "以下是总结：" 류
        # single 요약에서 관측된 중국어 지시문 패턴
        # 이 패턴들은 모델이 요약 방법을 중국어로 나레이션하는 메타 문구입니다.
        # 실제 한국어 문서 요약에는 절대 등장하지 않으므로 오탐 위험이 없습니다.
        # 단, 콜론(：) 이후 한국어가 같은 줄에 있는 경우는
        # _clean_summary_prefix의 CJK 콜론 패턴이 먼저 처리하므로
        # 여기에 도달했을 때는 이미 한국어 내용이 분리된 상태입니다.
        r"[^\n]*若要概括[^\n]*",              # "若要概括这段内容" 변형 전체
        r"[^\n]*请用韩语[^\n]*",              # "请用韩语总结/简要总结" 변형 전체
        r"[^\n]*概括这段[^\n]*",              # "概括这段内容" 변형 전체
        r"[^\n]*以下内容请[^\n]*",            # "以下内容请" 변형 전체
    ]
    for pattern in known_patterns:
        text = re.sub(pattern, "", text)

    # ── 2단계: 줄 단위 중국어 비율 검사 ─────────────────────────────────────────
    # CJK Unified Ideographs U+4E00–U+9FFF: 중국어 간체·번체, 일본어 한자, 한국어 한자 공통
    # Hangul Syllables U+AC00–U+D7A3: 한글 전용
    # 현대 한국어 문장에서 U+4E00–U+9FFF 범위 문자가 많다면 중국어 오염으로 간주합니다.
    #
    # 제거 조건 (둘 다 충족해야 제거):
    #   - 해당 줄의 한자(U+4E00-U+9FFF) 수가 4자 이상
    #   - CJK 문자(한자 + 한글) 중 한자 비율이 80% 초과
    # → 한국어 문장에 간간이 섞인 한자 용어(예: "人工知能")는 남기고,
    #   거의 전체가 중국어인 줄만 제거합니다.
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue
        chinese = sum(1 for c in stripped if "\u4e00" <= c <= "\u9fff")
        korean  = sum(1 for c in stripped if "\uac00" <= c <= "\ud7a3")
        total_cjk = chinese + korean
        if chinese >= 4 and total_cjk > 0 and chinese / total_cjk > 0.8:
            continue  # 중국어 오염 라인으로 판단하여 제거
        clean_lines.append(line)

    # 제거로 생긴 빈 줄이 3개 이상 연속되면 단락 구분자로 정규화합니다.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(clean_lines)).strip()


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


# ── 전처리 ───────────────────────────────────────────────────────────────────

def _preprocess_text(text: str) -> str:
    """
    요약 파이프라인 진입 전에 텍스트를 정규화합니다.

    PDF 추출이나 복사·붙여넣기 시 발생하는 과도한 공백·줄바꿈을 제거합니다.
    - 3개 이상 연속 줄바꿈 → \n\n (단락 구분자로 통일)
    - 연속 공백·탭 → 공백 1개

    효과:
    - chunk 분할이 단락 경계에서 더 깔끔하게 이루어집니다.
    - LLM에 전달되는 불필요한 토큰이 줄어 처리 속도가 소폭 개선됩니다.
    """
    text = re.sub(r"[ \t]+", " ", text)       # 연속 공백·탭 압축
    text = re.sub(r"\n{3,}", "\n\n", text)    # 3개 이상 줄바꿈을 단락 구분자로 정규화
    return text.strip()


# ── 동적 출력 길이 정책 ───────────────────────────────────────────────────────

def _target_sentences(chunk_count: int) -> str:
    """
    chunk 수에 따라 최종 merge 요약의 목표 문장 수 범위를 결정합니다.

    chunk 수를 기준으로 삼는 이유:
    - _summarize_chunked() 안에서 이미 계산된 값이라 추가 연산이 없습니다.
    - 1 chunk ≈ 1,000자이므로 사실상 글자 수에 비례합니다.

    증가 정책 (완만한 계단식):
    - chunk별 bullet 요약은 "3개 이내"로 그대로 유지합니다.
    - 오직 최종 merge 1회에서만 출력 길이를 조정합니다.
    - LLM 호출 횟수는 변하지 않습니다.

    chunk 수   목표 문장
    ──────────────────
     2         3~5   (기존 동일)
     3~4       5~7
     5~7       7~9
     8~10      9~11  (상한)
    """
    if chunk_count <= 2:
        return "3~5"
    elif chunk_count <= 4:
        return "5~7"
    elif chunk_count <= 7:
        return "7~9"
    else:
        return "9~11"


# ── chunk 단위 병렬 요약 워커 ─────────────────────────────────────────────────
#
# 모듈 수준 함수로 분리한 이유:
# ThreadPoolExecutor는 제출된 함수를 내부 스레드에서 호출합니다.
# 중첩 함수(클로저)는 Windows에서 pickle 직렬화 시 문제가 생길 수 있어,
# 모듈 수준 함수로 두는 것이 안전합니다.
#
# 이 함수는 _summarize_chunked()에서만 사용합니다.
# 인자로 (i, chunk, total)을 받고 (i, bullet_result)를 반환합니다.
# i를 함께 반환하는 이유: as_completed는 완료 순서로 결과를 내보내므로,
# 호출자가 원문 순서를 복원하려면 index가 필요합니다.

def _summarize_one_chunk(i: int, chunk: str, total: int) -> tuple[int, str]:
    """
    단일 chunk를 bullet 요약합니다. ThreadPoolExecutor의 워커 함수입니다.

    Returns:
        (i, bullet_result): 원문 순서 복원에 필요한 index와 요약 결과

    Raises:
        RuntimeError: Ollama 호출 실패 시. chunk 번호를 메시지에 포함합니다.
    """
    try:
        result = ollama.generate(_chunk_prompt(chunk), num_predict=250)
        return i, result
    except RuntimeError as e:
        raise RuntimeError(f"chunk {i}/{total} 요약 중 오류 발생: {e}")


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

    # 과도한 공백·줄바꿈을 정리해 chunking 품질과 처리 속도를 개선합니다.
    text = _preprocess_text(text)

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
    result = _strip_language_noise(_clean_summary_prefix(ollama.generate(_single_prompt(text))))
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

    # chunk 수에 따라 최종 요약의 목표 문장 수를 결정합니다.
    # chunk별 중간 요약은 그대로 짧게 유지하고, merge 단계에서만 출력량을 조정합니다.
    target_sentences = _target_sentences(total)

    steps.append(f"문서 분할 완료 ({total}개 chunk)")

    # ── chunk 병렬 요약 ────────────────────────────────────────────────────────
    #
    # max_workers는 settings.summarize_max_workers(.env의 SUMMARIZE_MAX_WORKERS)로
    # 제어합니다. OLLAMA_NUM_PARALLEL 환경변수와 같은 값으로 맞추는 것을 권장합니다.
    #
    # 순서 보장 설계:
    # - as_completed는 완료 순서로 future를 yield합니다 (원문 순서와 다를 수 있음).
    # - 각 future의 index를 futures dict에 보존하고, 결과를 results[i]에 저장합니다.
    # - 모든 future 완료 후 sorted(results)로 재조립해 원문 순서를 복원합니다.
    #
    # 실패 처리 전략 (fail-fast):
    # - 하나라도 실패하면 즉시 RuntimeError를 raise합니다.
    # - 이미 실행 중인 스레드는 완료될 때까지 계속 돌지만 결과는 버립니다.
    # - 부분 요약으로 merge를 만들면 최종 품질이 불균형해지므로 중단이 맞습니다.
    #
    # steps 로그 설계:
    # - "시작" 로그는 병렬 구간 진입 시 한 번만 남깁니다.
    # - "완료" 로그는 as_completed 순서대로 append합니다 (완료 순서 = 실제 흐름).
    # - 순서가 섞여도 됩니다. bullet_parts 최종 순서는 sorted()가 보장합니다.

    steps.append(
        f"chunk 병렬 요약 시작 ({total}개, 동시 {settings.summarize_max_workers}개)"
    )

    results: dict[int, str] = {}

    with ThreadPoolExecutor(max_workers=settings.summarize_max_workers) as executor:
        futures = {
            executor.submit(_summarize_one_chunk, i, chunk, total): i
            for i, chunk in enumerate(chunks, start=1)
        }

        for future in as_completed(futures):
            i = futures[future]
            try:
                idx, result = future.result()
                results[idx] = result
                steps.append(f"chunk {idx}/{total} 요약 완료")
            except RuntimeError as e:
                steps.append(f"chunk {i}/{total} 요약 실패")
                raise

    # index 순서대로 정렬해 원문 chunk 순서를 복원합니다.
    bullet_parts = [results[i] for i in sorted(results)]

    # 모든 chunk의 bullet 요약을 하나로 이어붙여 머지 프롬프트에 전달합니다.
    steps.append(f"최종 통합 요약 중 ({target_sentences}문장 목표)")
    try:
        # merge는 최종 요약이므로 문장 수 목표에 맞게 충분한 여유를 줍니다.
        # 9~11문장 기준 최대 ~600토큰이므로 700으로 상한합니다.
        final = _strip_language_noise(_clean_summary_prefix(ollama.generate(_merge_prompt("\n".join(bullet_parts), target_sentences), num_predict=700)))
    except RuntimeError as e:
        steps.append("최종 통합 요약 실패")
        raise RuntimeError(f"최종 통합 요약 중 오류 발생: {e}")

    steps.append("최종 요약 생성 완료")
    return SummarizeResponse(summary=final, steps=steps)
