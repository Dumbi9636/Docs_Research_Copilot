from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.models.user import User
from app.repositories import user_repository, refresh_token_repository
from app.schemas.auth import LoginRequest
from app.schemas.user import UserCreate


def register(db: Session, data: UserCreate) -> User:
    if user_repository.get_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 이메일입니다.",
        )
    return user_repository.create(db, data)


def login(db: Session, data: LoginRequest) -> tuple[str, str]:
    """
    로그인 처리.
    성공 시 (access_token, refresh_token) 튜플을 반환합니다.

    보안 원칙: 이메일 존재 여부와 비밀번호 오류를 동일한 메시지로 처리합니다.
    공격자가 이메일 존재 여부를 탐색하지 못하도록 하기 위함입니다.
    """
    user = user_repository.get_by_email(db, data.email)

    if not user or not verify_password(data.password, user.password_hash):
        # 사용자가 존재하는 경우에만 실패 카운트 증가
        if user:
            user_repository.increment_failed_login(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의해 주세요.",
        )

    access_token = create_access_token(user.user_id, user.role)
    refresh_token_value, expires_at = create_refresh_token(user.user_id)

    refresh_token_repository.create(db, user.user_id, refresh_token_value, expires_at)
    user_repository.update_last_login(db, user)

    return access_token, refresh_token_value


def refresh_access_token(db: Session, refresh_token_value: str) -> str:
    """
    Refresh Token으로 새 Access Token을 발급합니다.
    DB에서 토큰의 취소 여부를 확인한 후 발급합니다.
    """
    try:
        payload = decode_token(refresh_token_value)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 refresh token입니다.",
        )

    # type 클레임으로 access token이 잘못 전달되는 경우를 방어합니다.
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token이 아닙니다.",
        )

    token_record = refresh_token_repository.get_by_token_value(db, refresh_token_value)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="만료되었거나 취소된 refresh token입니다.",
        )

    user = user_repository.get_by_id(db, int(payload["sub"]))
    if not user or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 사용자입니다.",
        )

    return create_access_token(user.user_id, user.role)


def logout(db: Session, user_id: int) -> None:
    """해당 사용자의 모든 refresh token을 취소합니다."""
    refresh_token_repository.revoke_all_by_user(db, user_id)
