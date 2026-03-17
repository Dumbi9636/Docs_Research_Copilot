from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("이름을 입력해 주세요.")
        return v.strip()


class UserRead(BaseModel):
    """응답용 스키마 — 비밀번호 해시 제외."""
    user_id: int
    email: str
    name: str
    role: str           # USER / ADMIN
    status: str
    email_verified: str
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
