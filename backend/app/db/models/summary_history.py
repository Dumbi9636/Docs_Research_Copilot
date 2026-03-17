from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Sequence
from sqlalchemy.orm import relationship

from app.db.base import Base

_summary_history_seq = Sequence("SUMMARY_HISTORY_SEQ")


class SummaryHistory(Base):
    __tablename__ = "SUMMARY_HISTORY"

    history_id = Column(Integer, _summary_history_seq, primary_key=True)

    # 확정 정책: 비로그인 사용자 요약 불허 → NOT NULL
    user_id = Column(Integer, ForeignKey("USERS.user_id"), nullable=False)

    # 파일 업로드 시 채워짐. 텍스트 직접 입력 시 None.
    original_filename = Column(String(500), nullable=True)
    file_type = Column(String(20), nullable=True)   # txt/pdf/docx/image/text
    file_size = Column(Integer, nullable=True)       # bytes

    model_name = Column(String(100), nullable=False)
    summary_mode = Column(String(20), nullable=False)  # single / chunked
    input_chars = Column(Integer, nullable=False)

    # Oracle CLOB — SQLAlchemy Text 타입이 Oracle에서 CLOB으로 자동 매핑됨
    output_summary = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default="SUCCESS")
    error_message = Column(String(2000), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="summary_histories")
