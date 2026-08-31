"""Development/testing API for the research pipeline only."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research import ResearchProviderError, get_configured_source, research_topics

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/research", response_model=ResearchResponse)
def research(payload: ResearchRequest, db: DbSession):
    settings = get_settings()
    try:
        items = research_topics(
            db,
            payload.topics,
            get_configured_source(settings.research_timeout_seconds),
            freshness_days=payload.freshness_days or settings.research_window_days,
        )
        return {"items": items}
    except ResearchProviderError as exc:
        raise HTTPException(status_code=502, detail="Research provider is unavailable") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
