from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Ollama 설정
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_timeout: float = 120.0

    # CORS 설정
    frontend_origin: str = "http://localhost:3000"

    # 청킹 설정
    # 이 글자 수를 초과하면 chunk 분할 요약으로 전환합니다.
    chunk_threshold: int = 1500
    # chunk당 목표 글자 수 (단락/문장 경계를 우선하며 이 크기에 가깝게 분할합니다)
    target_chunk_size: int = 1000
    # 허용하는 최대 chunk 수. 초과 시 에러를 반환합니다.
    max_chunks: int = 10

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


settings = Settings()
