"""Database-backed post service used by the API routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.schemas.posts import PostCreate


class PostNotFoundError(Exception):
    """Raised when a requested post does not exist."""


def _get_post_or_raise(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PostNotFoundError("Post not found")
    return post


def create_post(db: Session, post: PostCreate) -> Post:
    db_post = Post(**post.model_dump())
    db.add(db_post)
    db.flush()
    db.refresh(db_post)
    return db_post


def get_posts(db: Session) -> list[Post]:
    return list(db.scalars(select(Post).order_by(Post.id)).all())


def get_post(db: Session, post_id: int) -> Post:
    return _get_post_or_raise(db, post_id)


def update_post(db: Session, post_id: int, updated_post: PostCreate) -> Post:
    db_post = _get_post_or_raise(db, post_id)
    for field, value in updated_post.model_dump().items():
        setattr(db_post, field, value)
    db.flush()
    db.refresh(db_post)
    return db_post


def delete_post(db: Session, post_id: int) -> None:
    db_post = _get_post_or_raise(db, post_id)
    db.delete(db_post)
    db.flush()
