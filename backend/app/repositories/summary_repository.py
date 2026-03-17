from sqlalchemy.orm import Session

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
    error_message: str | None = None,
    processing_time_ms: int | None = None,
) -> SummaryHistory:
    record = SummaryHistory(
        user_id=user_id,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        model_name=model_name,
        summary_mode=summary_mode,
        input_chars=input_chars,
        output_summary=output_summary,
        status=status,
        error_message=error_message,
        processing_time_ms=processing_time_ms,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


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
