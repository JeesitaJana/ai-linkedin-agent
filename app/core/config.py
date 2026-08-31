"""Application configuration for the FastAPI service."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

APP_TITLE = "AI LinkedIn Content Automation Agent"
APP_DESCRIPTION = "Backend for an AI-powered LinkedIn content automation system."
APP_VERSION = "0.1.0"


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    database_url: str
    research_provider: str
    research_timeout_seconds: float
    research_window_days: int


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    database_url = os.environ["DATABASE_URL"]
    return Settings(
        database_url=database_url,
        research_provider=os.getenv("RESEARCH_PROVIDER", "arxiv"),
        research_timeout_seconds=float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "10")),
        research_window_days=int(os.getenv("RESEARCH_WINDOW_DAYS", "30")),
    )
