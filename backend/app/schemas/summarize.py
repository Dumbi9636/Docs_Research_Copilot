from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    text: str


class SummarizeResponse(BaseModel):
    summary: str
    steps: list[str]
