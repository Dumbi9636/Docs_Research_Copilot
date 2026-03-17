from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Sequence
from sqlalchemy.orm import relationship

from app.db.base import Base

_refresh_tokens_seq = Sequence("REFRESH_TOKENS_SEQ")


class RefreshToken(Base):
    __tablename__ = "REFRESH_TOKENS"

    token_id = Column(Integer, _refresh_tokens_seq, primary_key=True)
    user_id = Column(Integer, ForeignKey("USERS.user_id"), nullable=False)

    # MVP: 원문(JWT 문자열) 그대로 저장
    token_value = Column(String(1000), nullable=False, unique=True)

    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(String(1), nullable=False, default="N")  # Y / N
    revoked_at = Column(DateTime, nullable=True)  # 취소 시점

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")
