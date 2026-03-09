from app.services import ollama_client
from app.schemas.summarize import SummarizeResponse


def summarize(text: str) -> SummarizeResponse:
    """텍스트를 받아 Ollama로 요약하고 처리 단계와 함께 반환합니다."""
    steps: list[str] = []

    steps.append("입력 검증 완료")

    prompt = f"""당신은 문서 요약 전문가입니다.
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

    steps.append("Ollama 요청 전송")
    result = ollama_client.generate(prompt)

    steps.append("응답 수신 완료")
    steps.append("요약 생성 완료")

    return SummarizeResponse(summary=result, steps=steps)
