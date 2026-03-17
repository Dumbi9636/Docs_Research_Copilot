from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.api import auth
from app.api import users
from app.core.config import settings

app = FastAPI(title="Docs Research Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(auth.router)
app.include_router(users.router)
