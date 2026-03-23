from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    text: str
    document_type: str | None = None  # general / legal / medical / technical 등


class SummarizeResponse(BaseModel):
    summary: str
    steps: list[str]
    history_id: int  # 저장된 SUMMARY_HISTORY PK — 다운로드 시 연결에 사용
