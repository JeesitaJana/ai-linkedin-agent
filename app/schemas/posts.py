"""Pydantic schemas for LinkedIn post resources."""

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Title of the LinkedIn post",
    )

    content: str = Field(
        min_length=1,
        max_length=3000,
        description="Main content of the LinkedIn post",
    )

    hashtags: list[str] = Field(
        default_factory=list,
        description="Hashtags associated with the post",
    )

    approved: bool = False


class PostResponse(PostCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
