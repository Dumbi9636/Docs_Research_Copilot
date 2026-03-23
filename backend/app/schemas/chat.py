from typing import Literal
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    history_id: int
    messages: list[ChatMessage]  # 이전 대화 (첫 질문이면 빈 리스트)
    question: str


class ChatResponse(BaseModel):
    answer: str
