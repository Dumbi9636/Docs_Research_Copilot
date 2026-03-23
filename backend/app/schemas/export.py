from typing import Literal

from pydantic import BaseModel


class ExportRequest(BaseModel):
    summary: str
    format: Literal["txt", "docx", "pdf"]
    source_filename: str = ""
    history_id: int | None = None  # 연결할 SUMMARY_HISTORY PK (선택)
    skip_log: bool = False          # True이면 DOWNLOAD_LOGS에 저장하지 않음 (재다운로드 시 사용)
