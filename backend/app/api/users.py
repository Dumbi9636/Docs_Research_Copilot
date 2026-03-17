from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import summary_repository
from app.schemas.history import SummaryHistoryRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    """
    내 정보 조회.
    role 포함 — 프론트에서 ADMIN 메뉴 노출 여부 판단에 활용 가능합니다.
    """
    return current_user


@router.get("/me/summaries", response_model=list[SummaryHistoryRead])
def get_my_summaries(
    skip: int = Query(default=0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(default=20, ge=1, le=100, description="최대 반환 수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    내 요약 이력 조회 (최신순).
    skip/limit으로 페이징합니다.
    """
    return summary_repository.get_by_user_id(
        db, current_user.user_id, skip=skip, limit=limit
    )
