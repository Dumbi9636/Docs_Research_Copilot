from typing import Literal
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    history_id: int
    messages: list[ChatMessage]  # 이전 대화 (첫 질문이면 빈 리스트)
    question: str
    # strict: 문서 근거만 답변 / chat: 문서 근거 + 제한적 해석·일반 설명 허용 (기본값)
    mode: Literal["strict", "chat"] = "chat"


class ChatResponse(BaseModel):
    answer: str
