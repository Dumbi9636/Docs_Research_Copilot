# 환경설정 모듈
# 하드코딩 대신 환경변수(.env)로 값을 관리하면,
# 개발/운영 환경마다 코드 변경 없이 동작을 바꿀 수 있습니다.

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ 기준으로 .env 경로를 계산합니다.
# 이렇게 하면 서버를 어느 디렉터리에서 실행하든 항상
# 'backend/.env'를 정확히 찾을 수 있습니다.
# (os.getcwd() 기준으로 하면 실행 위치에 따라 경로가 달라집니다)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # ── Ollama 설정 ─────────────────────────────────────────────────────────
    # Ollama 서버 주소. 로컬 기본 포트는 11434입니다.
    ollama_base_url: str = "http://localhost:11434"
    # 사용할 LLM 모델 이름. 'ollama pull <모델명>'으로 미리 설치해야 합니다.
    ollama_model: str = "llama3"
    # Ollama 응답 대기 최대 시간(초). LLM 추론은 느릴 수 있어 넉넉히 설정합니다.
    ollama_timeout: float = 120.0

    # ── CORS 설정 ────────────────────────────────────────────────────────────
    # 브라우저가 API를 호출할 수 있도록 허용할 프론트엔드 출처입니다.
    frontend_origin: str = "http://localhost:3000"

    # ── 청킹 설정 ────────────────────────────────────────────────────────────
    # 이 글자 수를 초과하면 chunk 분할 요약으로 전환합니다.
    # LLM은 컨텍스트 한계가 있어, 너무 긴 텍스트는 한 번에 처리하기 어렵습니다.
    chunk_threshold: int = 1500
    # chunk당 목표 글자 수 (단락/문장 경계를 우선하며 이 크기에 가깝게 분할합니다)
    target_chunk_size: int = 1000
    # 허용하는 최대 chunk 수. 초과 시 에러를 반환합니다.
    # 무제한 허용 시 LLM 호출이 과도하게 발생할 수 있어 상한을 둡니다.
    max_chunks: int = 10

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


# 모듈 로드 시 한 번만 생성되는 싱글턴 인스턴스입니다.
# 다른 모듈에서 'from app.core.config import settings'로 임포트해 사용합니다.
# 매번 새 인스턴스를 만들지 않으므로 .env를 한 번만 읽습니다.
settings = Settings()
