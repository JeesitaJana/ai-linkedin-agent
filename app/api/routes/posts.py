"""Post CRUD API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.posts import PostCreate, PostResponse
from app.services import posts as post_service
from app.services.posts import PostNotFoundError

router = APIRouter()

not_found_response = {404: {"description": "Post not found"}}
DbSession = Annotated[Session, Depends(get_db)]


def _raise_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Post not found",
    )


def _handle_database_error(exc: SQLAlchemyError) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database operation failed",
    ) from exc


@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post(post: PostCreate, db: DbSession):
    try:
        return post_service.create_post(db, post)
    except SQLAlchemyError as exc:
        _handle_database_error(exc)


@router.get(
    "/posts",
    response_model=list[PostResponse],
)
def get_posts(db: DbSession):
    try:
        return post_service.get_posts(db)
    except SQLAlchemyError as exc:
        _handle_database_error(exc)


@router.get(
    "/posts/{post_id}",
    response_model=PostResponse,
    responses=not_found_response,
)
def get_post(post_id: int, db: DbSession):
    try:
        return post_service.get_post(db, post_id)
    except PostNotFoundError:
        _raise_not_found()
    except SQLAlchemyError as exc:
        _handle_database_error(exc)


@router.put(
    "/posts/{post_id}",
    response_model=PostResponse,
    responses=not_found_response,
)
def update_post(post_id: int, updated_post: PostCreate, db: DbSession):
    try:
        return post_service.update_post(db, post_id, updated_post)
    except PostNotFoundError:
        _raise_not_found()
    except SQLAlchemyError as exc:
        _handle_database_error(exc)


@router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=not_found_response,
)
def delete_post(post_id: int, db: DbSession):
    try:
        post_service.delete_post(db, post_id)
    except PostNotFoundError:
        _raise_not_found()
    except SQLAlchemyError as exc:
        _handle_database_error(exc)
