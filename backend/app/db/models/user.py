from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Sequence
from sqlalchemy.orm import relationship

from app.db.base import Base

# Oracle 11g 호환: IDENTITY 대신 SEQUENCE + TRIGGER 방식 사용
# DB에 USERS_SEQ 시퀀스가 생성되어 있어야 합니다.
_users_seq = Sequence("USERS_SEQ")


class User(Base):
    __tablename__ = "USERS"

    user_id = Column(Integer, _users_seq, primary_key=True)
    email = Column(String(320), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    name = Column(String(100), nullable=False)

    # role: 기본값 USER, 관리자는 ADMIN
    # 회원가입 시 서버에서 항상 'USER'로 고정하며, 외부에서 임의 변경 불가
    role = Column(String(20), nullable=False, default="USER")

    status = Column(String(20), nullable=False, default="ACTIVE")

    # email_verified: MVP에서는 컬럼만 유지, 실제 인증 제한 로직은 미적용
    email_verified = Column(String(1), nullable=False, default="N")

    failed_login_count = Column(Integer, nullable=False, default=0)
    last_login_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # relationships
    summary_histories = relationship(
        "SummaryHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
