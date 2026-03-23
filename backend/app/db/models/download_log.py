from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Sequence
from sqlalchemy.orm import relationship

from app.db.base import Base

_download_logs_seq = Sequence("DOWNLOAD_LOGS_SEQ")


class DownloadLog(Base):
    __tablename__ = "DOWNLOAD_LOGS"

    download_id = Column(Integer, _download_logs_seq, primary_key=True)

    user_id = Column(Integer, ForeignKey("USERS.user_id"), nullable=False)
    history_id = Column(Integer, ForeignKey("SUMMARY_HISTORY.history_id"), nullable=True)

    # 다운로드 시점의 원본 파일명 (source_filename)
    file_name = Column(String(500), nullable=True)

    # 내보낸 형식: txt / docx / pdf
    download_format = Column(String(10), nullable=False)

    status = Column(String(20), nullable=False, default="SUCCESS")
    error_message = Column(String(2000), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="download_logs")
    summary_history = relationship("SummaryHistory", back_populates="download_logs")
