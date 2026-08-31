"""Schemas for normalized research input and output."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ResearchRequest(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=50)
    freshness_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[str]) -> list[str]:
        normalized = [topic.strip() for topic in value]
        if any(not topic for topic in normalized):
            raise ValueError("topics must not contain empty values")
        if len({topic.casefold() for topic in normalized}) != len(normalized):
            raise ValueError("topics must not contain duplicates")
        return normalized


class ResearchItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    topic: str
    title: str
    summary: str
    source_name: str
    source_url: HttpUrl
    published_at: datetime | None
    discovered_at: datetime
    relevance_score: float | None
    source_type: str
    metadata: dict[str, object] = Field(default_factory=dict, validation_alias="metadata_json", serialization_alias="metadata")


class ResearchResponse(BaseModel):
    items: list[ResearchItemResponse]
