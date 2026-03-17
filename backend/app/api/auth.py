from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    AccessTokenResponse,
)
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """
    회원가입.
    - role은 서버에서 항상 USER로 고정됩니다.
    - 이메일 중복 시 400을 반환합니다.
    """
    user = auth_service.register(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    로그인.
    성공 시 access_token(30분)과 refresh_token(7일)을 반환합니다.
    """
    access_token, refresh_token = auth_service.login(db, data)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    """
    Access Token 재발급.
    유효한 refresh_token을 전달하면 새 access_token을 반환합니다.
    """
    access_token = auth_service.refresh_access_token(db, data.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    로그아웃.
    해당 사용자의 모든 refresh token을 취소합니다.
    클라이언트는 보유 중인 access/refresh token을 파기해야 합니다.
    """
    auth_service.logout(db, current_user.user_id)
