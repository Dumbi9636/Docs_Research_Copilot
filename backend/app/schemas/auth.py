from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """로그인 성공 시 반환. access + refresh 토큰 모두 포함."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """refresh 재발급 시 반환. access token만 갱신."""
    access_token: str
    token_type: str = "bearer"
