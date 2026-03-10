# Ollama HTTP 클라이언트 모듈
#
# 이 파일의 역할: Ollama 서버와의 HTTP 통신만 전담합니다.
# 비즈니스 로직(무엇을 요약할지 등)은 여기 없고,
# "Ollama에 요청을 보내고 텍스트를 받아오는 것"만 합니다.
#
# 외부 라이브러리(httpx)의 다양한 예외를 RuntimeError 하나로 통일합니다.
# 덕분에 상위 계층(services, routes)은 httpx를 전혀 몰라도 되고,
# RuntimeError 하나만 처리하면 됩니다.

import httpx
from app.core.config import settings


def generate(prompt: str) -> str:
    """
    Ollama /api/generate 엔드포인트를 호출하고 응답 텍스트를 반환합니다.

    Args:
        prompt: LLM에 전달할 프롬프트 문자열

    Returns:
        LLM이 생성한 응답 텍스트

    Raises:
        RuntimeError: 연결 실패, 타임아웃, 모델 없음, 빈 응답 등
                      모든 Ollama 관련 오류를 RuntimeError로 변환합니다.
    """
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,  # 스트리밍 없이 응답 전체를 한 번에 받습니다.
    }

    # ── 네트워크 수준 예외 처리 ──────────────────────────────────────────────
    # httpx 고유 예외를 RuntimeError로 변환합니다.
    # 상위 계층은 httpx를 임포트하지 않아도 됩니다.
    try:
        response = httpx.post(url, json=payload, timeout=settings.ollama_timeout)
    except httpx.ConnectError:
        # Ollama 서버가 꺼져 있거나 주소가 잘못된 경우
        raise RuntimeError("Ollama 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.")
    except httpx.TimeoutException:
        # LLM 추론이 ollama_timeout 초를 초과한 경우
        raise RuntimeError("Ollama 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")

    # ── HTTP 상태 코드 수준 예외 처리 ────────────────────────────────────────
    if response.status_code == 404:
        # Ollama는 존재하지 않는 모델 요청 시 404를 반환합니다.
        raise RuntimeError(
            f"모델 '{settings.ollama_model}'을 찾을 수 없습니다. "
            f"'ollama pull {settings.ollama_model}' 명령으로 모델을 설치해 주세요."
        )

    try:
        response.raise_for_status()  # 4xx/5xx 응답을 예외로 변환합니다.
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama 서버 오류가 발생했습니다. (HTTP {e.response.status_code})")

    # ── 응답 본문 파싱 ───────────────────────────────────────────────────────
    data = response.json()
    result = data.get("response", "").strip()

    # Ollama가 200을 반환하더라도 응답이 비어 있을 수 있습니다.
    if not result:
        raise RuntimeError("Ollama 모델이 빈 응답을 반환했습니다. 모델 상태를 확인해 주세요.")

    return result
