"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, posts, research, schedules
from app.core.config import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from app.database.session import get_session_factory
from app.services.scheduler import get_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = get_scheduler(get_session_factory())
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(posts.router)
app.include_router(schedules.router)
app.include_router(research.router)
