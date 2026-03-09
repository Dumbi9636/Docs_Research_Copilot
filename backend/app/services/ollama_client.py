import httpx

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3"


def generate(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Ollama /api/generate 엔드포인트를 호출하고 응답 텍스트를 반환합니다."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = httpx.post(url, json=payload, timeout=120.0)
    except httpx.ConnectError:
        raise RuntimeError("Ollama 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.")
    except httpx.TimeoutException:
        raise RuntimeError("Ollama 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")

    if response.status_code == 404:
        raise RuntimeError(f"모델 '{model}'을 찾을 수 없습니다. 'ollama pull {model}' 명령으로 모델을 설치해 주세요.")

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama 서버 오류가 발생했습니다. (HTTP {e.response.status_code})")

    data = response.json()
    result = data.get("response", "").strip()

    if not result:
        raise RuntimeError("Ollama 모델이 빈 응답을 반환했습니다. 모델 상태를 확인해 주세요.")

    return result
