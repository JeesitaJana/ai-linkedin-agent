"""Content generation API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.schemas.posts import PostResponse
from app.services.content_generation import ContentGenerationError, generate_post_from_research
from app.services.research import get_configured_source, research_topics

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


class ContentGenerationRequest(BaseModel):
    """Request schema for content generation."""
    topics: list[str] = Field(min_length=1, max_length=50, description="Topics to research and generate content about")
    freshness_days: int | None = Field(default=None, ge=1, le=3650, description="Freshness period for research in days")


@router.post(
    "/generate-post",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_post(
    request: ContentGenerationRequest,
    db: DbSession,
):
    """Generate a LinkedIn post from research on the given topics."""
    try:
        settings = get_settings()
        
        # First, perform research
        research_items = research_topics(
            db,
            request.topics,
            get_configured_source(settings.research_timeout_seconds),
            freshness_days=request.freshness_days or settings.research_window_days,
        )
        
        if not research_items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No research items found for the given topics"
            )
        
        # Generate post from research
        post = generate_post_from_research(db, research_items, request.topics[0])
        
        return post
        
    except ContentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        ) from exc