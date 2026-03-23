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

    # 요약 전 추출된 원문 텍스트. 문서 기반 Q&A(/chat)의 컨텍스트로 사용됩니다.
    # 파일 업로드 시 추출된 텍스트, 직접 입력 시 입력 텍스트 그대로 저장됩니다.
    # NULL: 이 컬럼 추가 전에 생성된 기존 기록 → /chat에서 요약문 fallback 처리합니다.
    input_text = Column(Text, nullable=True)

    document_type = Column(String(50), nullable=True)   # general / legal / medical / technical 등

    status = Column(String(20), nullable=False, default="SUCCESS")
    error_message = Column(String(2000), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="summary_histories")
    download_logs = relationship("DownloadLog", back_populates="summary_history")
