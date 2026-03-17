from collections.abc import Generator

import oracledb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# ── Thick mode 초기화 ──────────────────────────────────────────────────────────
# Thick mode는 Oracle Instant Client(또는 Full Client)가 설치되어 있어야 합니다.
# create_engine() 호출보다 반드시 먼저 실행되어야 합니다.
#
# lib_dir 우선순위:
#   1. .env의 ORACLE_CLIENT_LIB_DIR이 지정된 경우 → 해당 경로 사용
#   2. 빈 값인 경우 → PATH / LD_LIBRARY_PATH 에서 자동 탐색
#      (Instant Client를 PATH에 추가해두면 lib_dir 생략 가능)
_lib_dir = settings.oracle_client_lib_dir.strip() or None
oracledb.init_oracle_client(lib_dir=_lib_dir)

# ── Engine ─────────────────────────────────────────────────────────────────────
_DATABASE_URL = (
    f"oracle+oracledb://{settings.oracle_user}:{settings.oracle_password}"
    f"@{settings.oracle_dsn}"
)

engine = create_engine(
    _DATABASE_URL,
    echo=False,           # SQL 로깅: 개발 시 True로 변경 가능
    pool_pre_ping=True,   # 세션 만료 대응 — 연결 사용 전 유효성 확인
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency — 요청마다 DB 세션을 열고, 응답 후 반드시 닫습니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
