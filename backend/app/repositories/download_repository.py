from sqlalchemy.orm import Session

from app.db.models.download_log import DownloadLog


def create(
    db: Session,
    user_id: int,
    download_format: str,
    file_name: str | None = None,
    history_id: int | None = None,
    status: str = "SUCCESS",
    error_message: str | None = None,
) -> DownloadLog:
    record = DownloadLog(
        user_id=user_id,
        history_id=history_id,
        file_name=file_name,
        download_format=download_format,
        status=status,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_by_id(db: Session, download_id: int) -> DownloadLog | None:
    return db.query(DownloadLog).filter(DownloadLog.download_id == download_id).first()


def delete(db: Session, record: DownloadLog) -> None:
    db.delete(record)
    db.commit()


def get_by_user_id(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
) -> list[DownloadLog]:
    return (
        db.query(DownloadLog)
        .filter(DownloadLog.user_id == user_id)
        .order_by(DownloadLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
