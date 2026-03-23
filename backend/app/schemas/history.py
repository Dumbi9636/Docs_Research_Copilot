from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class SummaryHistoryRead(BaseModel):
    """마이페이지 요약 이력 조회용 응답 스키마."""
    history_id: int
    original_filename: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    document_type: Optional[str]
    model_name: str
    summary_mode: str
    input_chars: int
    output_summary: Optional[str]
    status: str
    error_message: Optional[str]
    processing_time_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class DownloadLogRead(BaseModel):
    """마이페이지 다운로드 이력 조회용 응답 스키마."""
    download_id: int
    history_id: Optional[int]        # 연결된 요약 이력 PK (없으면 None)
    file_name: Optional[str]
    download_format: str
    status: str
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityItem(BaseModel):
    """요약 + 다운로드 통합 활동 이력 단일 항목."""
    activity_type: Literal["SUMMARY", "DOWNLOAD"]
    id: int                          # history_id 또는 download_id
    file_name: Optional[str]
    status: str
    created_at: datetime
    # SUMMARY 전용
    document_type: Optional[str] = None
    file_type: Optional[str] = None
    summary_mode: Optional[str] = None
    summary_text: Optional[str] = None      # 요약 결과 전문
    # DOWNLOAD 전용
    download_format: Optional[str] = None
    linked_history_id: Optional[int] = None  # 어떤 요약에서 내보냈는지
    # 공통
    error_message: Optional[str] = None
