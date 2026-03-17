from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.db.models.user import User

# tokenUrl은 Swagger UI의 Authorize 버튼에 표시되는 경로입니다.
# 실제 로그인은 JSON body를 받으므로 Swagger Authorize 버튼과 직접 연동되지 않지만,
# Bearer 토큰을 수동 입력하면 인증된 엔드포인트를 테스트할 수 있습니다.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    모든 인증 필요 라우트에 주입하는 Dependency.

    - JWT 서명 및 만료 검증
    - payload의 sub(user_id)로 DB에서 사용자 조회
    - status가 ACTIVE가 아니면 거부
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exception

    # import를 함수 내부에 두어 순환 import 방지
    from app.repositories import user_repository

    user = user_repository.get_by_id(db, user_id)
    if not user or user.status != "ACTIVE":
        raise credentials_exception

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    ADMIN 전용 라우트에 주입하는 Dependency.
    get_current_user를 먼저 통과한 뒤 role을 추가로 검사합니다.

    사용 예:
        @router.get("/admin/users")
        def list_users(admin: User = Depends(require_admin)):
            ...
    """
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return current_user
