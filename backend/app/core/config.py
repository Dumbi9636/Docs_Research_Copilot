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
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_timeout: float = 180.0

    # ── CORS 설정 ────────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:3000"

    # ── 청킹 설정 ────────────────────────────────────────────────────────────
    chunk_threshold: int = 1500
    target_chunk_size: int = 2000
    max_chunks: int = 10
    summarize_max_workers: int = 1

    # ── Oracle DB 설정 ───────────────────────────────────────────────────────
    # DSN 형식: host:port/service_name (예: localhost:1521/XE)
    oracle_user: str = "your_db_user"
    oracle_password: str = "your_db_password"
    oracle_dsn: str = "localhost:1521/XE"

    # Thick mode용 Oracle Instant Client 경로 (Windows 기준)
    # 예: C:\oracle\instantclient_21_12
    # 빈 문자열이면 PATH 환경변수에서 자동 탐색합니다.
    oracle_client_lib_dir: str = ""

    # ── JWT 설정 ─────────────────────────────────────────────────────────────
    # 운영 환경에서는 반드시 환경변수로 교체해야 합니다.
    jwt_secret_key: str = "change-this-to-a-long-random-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


# 모듈 로드 시 한 번만 생성되는 싱글턴 인스턴스입니다.
# 다른 모듈에서 'from app.core.config import settings'로 임포트해 사용합니다.
# 매번 새 인스턴스를 만들지 않으므로 .env를 한 번만 읽습니다.
settings = Settings()
