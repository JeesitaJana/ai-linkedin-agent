"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.routes import health, posts
from app.core.config import APP_DESCRIPTION, APP_TITLE, APP_VERSION


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

app.include_router(health.router)
app.include_router(posts.router)
