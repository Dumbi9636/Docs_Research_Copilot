from typing import Literal

from pydantic import BaseModel


class ExportRequest(BaseModel):
    summary: str
    format: Literal["txt", "docx", "pdf"]
    source_filename: str = ""
