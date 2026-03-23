from sqlalchemy.orm import Session

from app.db.models.download_log import DownloadLog
from app.db.models.summary_history import SummaryHistory


def create(
    db: Session,
    user_id: int,
    model_name: str,
    summary_mode: str,
    input_chars: int,
    output_summary: str,
    status: str = "SUCCESS",
    original_filename: str | None = None,
    file_type: str | None = None,
    file_size: int | None = None,
    document_type: str | None = None,
    error_message: str | None = None,
    processing_time_ms: int | None = None,
    input_text: str | None = None,
) -> SummaryHistory:
    record = SummaryHistory(
        user_id=user_id,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        document_type=document_type,
        model_name=model_name,
        summary_mode=summary_mode,
        input_chars=input_chars,
        output_summary=output_summary,
        status=status,
        error_message=error_message,
        processing_time_ms=processing_time_ms,
        input_text=input_text,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_by_id(db: Session, history_id: int) -> SummaryHistory | None:
    return db.query(SummaryHistory).filter(SummaryHistory.history_id == history_id).first()


def delete(db: Session, record: SummaryHistory) -> None:
    # DOWNLOAD_LOGS의 FK(history_id)를 먼저 NULL로 초기화해야 Oracle FK 제약 오류를 방지합니다.
    db.query(DownloadLog).filter(DownloadLog.history_id == record.history_id).update(
        {DownloadLog.history_id: None}
    )
    db.delete(record)
    db.commit()


def get_by_user_id(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
) -> list[SummaryHistory]:
    return (
        db.query(SummaryHistory)
        .filter(SummaryHistory.user_id == user_id)
        .order_by(SummaryHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
