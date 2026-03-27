from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models.refresh_token import RefreshToken

# token 발급
def create(
    db: Session,
    user_id: int,
    token_value: str,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_value=token_value,
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_by_token_value(db: Session, token_value: str) -> RefreshToken | None:
    """유효한(취소되지 않은) 토큰만 반환합니다."""
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_value == token_value,
            RefreshToken.is_revoked == "N",
        )
        .first()
    )


def revoke_all_by_user(db: Session, user_id: int) -> None:
    """
    해당 사용자의 모든 유효 토큰을 일괄 취소합니다.
    로그아웃 시 호출해 모든 디바이스 세션을 무효화합니다.
    """
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == "N",
    ).update(
        {"is_revoked": "Y", "revoked_at": datetime.utcnow()},
        synchronize_session=False,
    )
    db.commit()
