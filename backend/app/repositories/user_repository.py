from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.user import User
from app.schemas.user import UserCreate


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.user_id == user_id).first()


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create(db: Session, data: UserCreate) -> User:
    """
    회원가입 처리.
    role은 항상 'USER'로 고정 — 외부 입력값을 절대 사용하지 않습니다.
    """
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: User) -> None:
    """로그인 성공 시 마지막 로그인 시각 갱신 및 실패 횟수 초기화."""
    user.last_login_at = datetime.utcnow()
    user.failed_login_count = 0
    db.commit()


def increment_failed_login(db: Session, user: User) -> None:
    """로그인 실패 시 실패 횟수 1 증가."""
    user.failed_login_count += 1
    db.commit()
