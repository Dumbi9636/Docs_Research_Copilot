from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import summary_repository, download_repository
from app.schemas.history import ActivityItem, DownloadLogRead, SummaryHistoryRead
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


@router.get("/me/downloads", response_model=list[DownloadLogRead])
def get_my_downloads(
    skip: int = Query(default=0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(default=20, ge=1, le=100, description="최대 반환 수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    내 다운로드 이력 조회 (최신순).
    linked_history_id로 어떤 요약 결과를 내보냈는지 추적할 수 있습니다.
    """
    return download_repository.get_by_user_id(
        db, current_user.user_id, skip=skip, limit=limit
    )


@router.get("/me/activity", response_model=list[ActivityItem])
def get_my_activity(
    limit: int = Query(default=40, ge=1, le=100, description="최대 반환 수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    요약 + 다운로드 통합 활동 이력 조회 (최신순).
    activity_type 필드로 SUMMARY / DOWNLOAD 구분합니다.
    """
    summaries = summary_repository.get_by_user_id(db, current_user.user_id, limit=limit)
    downloads = download_repository.get_by_user_id(db, current_user.user_id, limit=limit)

    items: list[ActivityItem] = []

    for s in summaries:
        items.append(ActivityItem(
            activity_type="SUMMARY",
            id=s.history_id,
            file_name=s.original_filename,
            status=s.status,
            created_at=s.created_at,
            document_type=s.document_type,
            file_type=s.file_type,
            summary_mode=s.summary_mode,
            summary_text=s.output_summary,
            error_message=s.error_message,
        ))

    for d in downloads:
        # linked_history_id가 있으면 원본 요약문을 함께 포함합니다.
        # 원본 요약이 삭제된 경우 None으로 처리되어 재다운로드 버튼이 표시되지 않습니다.
        linked_summary_text = None
        if d.history_id:
            linked = summary_repository.get_by_id(db, d.history_id)
            if linked:
                linked_summary_text = linked.output_summary

        items.append(ActivityItem(
            activity_type="DOWNLOAD",
            id=d.download_id,
            file_name=d.file_name,
            status=d.status,
            created_at=d.created_at,
            download_format=d.download_format,
            linked_history_id=d.history_id,
            summary_text=linked_summary_text,
            error_message=d.error_message,
        ))

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:limit]


@router.delete("/me/summaries/{history_id}", status_code=204)
def delete_my_summary(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    내 요약 이력 삭제.
    연결된 다운로드 이력의 history_id는 NULL로 초기화됩니다.
    """
    record = summary_repository.get_by_id(db, history_id)
    if record is None or record.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다.")
    summary_repository.delete(db, record)


@router.delete("/me/downloads/{download_id}", status_code=204)
def delete_my_download(
    download_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """내 다운로드 이력 삭제."""
    record = download_repository.get_by_id(db, download_id)
    if record is None or record.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다.")
    download_repository.delete(db, record)
