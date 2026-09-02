"""Content generation API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.models.research_item import ResearchItem
from app.schemas.posts import PostResponse
from app.services.content_generation import ContentGenerationError, generate_post_from_research
from app.services.research import get_configured_source, research_topics

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


class ContentGenerationRequest(BaseModel):
    """Request schema for content generation."""

    topics: list[str] = Field(default_factory=list, max_length=50, description="Topics to research and generate content about")
    research_item_ids: list[int] | None = Field(default=None, description="Existing research item IDs to generate from")
    freshness_days: int | None = Field(default=None, ge=1, le=3650, description="Freshness period for research in days")
    instructions: str | None = Field(default=None, max_length=1000, description="Optional writing guidance for the content generator")

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[str]) -> list[str]:
        normalized = [topic.strip() for topic in value]
        if any(not topic for topic in normalized):
            raise ValueError("topics must not contain empty values")
        return normalized

    @field_validator("research_item_ids")
    @classmethod
    def validate_research_item_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("research_item_ids must not be empty when provided")
        if len(set(value)) != len(value):
            raise ValueError("research_item_ids must not contain duplicates")
        if any(item_id <= 0 for item_id in value):
            raise ValueError("research_item_ids must be positive integers")
        return value

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("instructions must not be empty when provided")
        return normalized


@router.post(
    "/generate-post",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_post(
    request: ContentGenerationRequest,
    db: DbSession,
):
    """Generate a LinkedIn post from research on the given topics or research item IDs."""
    try:
        if request.research_item_ids:
            db_items = db.scalars(
                select(ResearchItem).where(ResearchItem.id.in_(request.research_item_ids))
            ).all()
            selected_ids = {item.id for item in db_items}
            missing_ids = [item_id for item_id in request.research_item_ids if item_id not in selected_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Research item(s) not found: {missing_ids}",
                )
            research_items = list(db_items)
            topic = request.topics[0] if request.topics else research_items[0].topic
            post = generate_post_from_research(db, research_items, topic, instructions=request.instructions)
            return post

        if not request.topics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either topics or research_item_ids must be provided",
            )

        settings = get_settings()
        research_items = research_topics(
            db,
            request.topics,
            get_configured_source(settings.research_timeout_seconds),
            freshness_days=request.freshness_days or settings.research_window_days,
        )

        if not research_items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No research items found for the given topics",
            )

        post = generate_post_from_research(db, research_items, request.topics[0], instructions=request.instructions)
        return post

    except HTTPException:
        raise
    except ContentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc