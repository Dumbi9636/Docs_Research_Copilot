# 모든 모델을 여기서 import해야 alembic이 테이블 변경을 감지합니다.
from app.db.models.user import User  # noqa: F401
from app.db.models.summary_history import SummaryHistory  # noqa: F401
from app.db.models.refresh_token import RefreshToken  # noqa: F401
