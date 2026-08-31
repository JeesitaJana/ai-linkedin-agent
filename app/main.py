from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


app = FastAPI(
    title="AI LinkedIn Content Automation Agent",
    description="Backend for an AI-powered LinkedIn content automation system.",
    version="0.1.0",
)


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
    id: int


posts = []


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post(post: PostCreate):
    post_id = len(posts) + 1

    post_data = {
        "id": post_id,
        **post.model_dump(),
    }

    posts.append(post_data)

    return post_data


@app.get(
    "/posts",
    response_model=list[PostResponse],
)
def get_posts():
    return posts


@app.get(
    "/posts/{post_id}",
    response_model=PostResponse,
)
def get_post(post_id: int):
    for post in posts:
        if post["id"] == post_id:
            return post

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Post not found",
    )


@app.put(
    "/posts/{post_id}",
    response_model=PostResponse,
)
def update_post(post_id: int, updated_post: PostCreate):
    for index, post in enumerate(posts):
        if post["id"] == post_id:
            posts[index] = {
                "id": post_id,
                **updated_post.model_dump(),
            }

            return posts[index]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Post not found",
    )


@app.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_post(post_id: int):
    for index, post in enumerate(posts):
        if post["id"] == post_id:
            posts.pop(index)
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Post not found",
    )