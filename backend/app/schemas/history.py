from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SummaryHistoryRead(BaseModel):
    """마이페이지 요약 이력 조회용 응답 스키마."""
    history_id: int
    original_filename: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    model_name: str
    summary_mode: str
    input_chars: int
    output_summary: Optional[str]
    status: str
    error_message: Optional[str]
    processing_time_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
