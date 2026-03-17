from datetime import datetime, timedelta

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 비밀번호 ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, role: str) -> str:
    """
    Access Token을 생성합니다.
    payload에 user_id(sub)와 role을 포함해 DB 조회 없이 권한 분기가 가능합니다.
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """
    Refresh Token과 만료 시각을 함께 반환합니다.
    반환된 만료 시각은 DB에 저장해 revoke 여부 확인에 사용합니다.
    """
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return token, expire


def decode_token(token: str) -> dict:
    """
    토큰을 디코딩해 payload를 반환합니다.
    서명 불일치나 만료 시 JWTError를 발생시킵니다.
    호출부에서 JWTError를 catch해 적절한 HTTP 예외로 변환해야 합니다.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
