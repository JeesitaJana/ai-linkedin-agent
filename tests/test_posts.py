import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.post import Post


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def post_payload():
    return {
        "title": "AI in medical imaging",
        "content": "AI is helping clinicians analyze medical images more efficiently.",
        "hashtags": ["AI", "HealthTech"],
        "approved": False,
    }


def create_post(client: TestClient, payload: dict) -> dict:
    response = client.post("/posts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_post_success(client, post_payload):
    response = client.post("/posts", json=post_payload)

    assert response.status_code == 201
    assert response.json() == {"id": 1, **post_payload}


def test_create_post_invalid_title_and_content(client):
    response = client.post(
        "/posts",
        json={"title": "", "content": "", "hashtags": [], "approved": False},
    )

    assert response.status_code == 422


def test_get_posts(client, post_payload):
    created_post = create_post(client, post_payload)

    response = client.get("/posts")

    assert response.status_code == 200
    assert response.json() == [created_post]


def test_get_post_success(client, post_payload):
    created_post = create_post(client, post_payload)

    response = client.get(f"/posts/{created_post['id']}")

    assert response.status_code == 200
    assert response.json() == created_post


def test_get_post_missing_returns_404(client):
    response = client.get("/posts/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


def test_update_post_success(client, post_payload):
    created_post = create_post(client, post_payload)
    updated_payload = {
        "title": "Updated AI post",
        "content": "Updated content for a LinkedIn post about AI.",
        "hashtags": ["AI"],
        "approved": True,
    }

    response = client.put(f"/posts/{created_post['id']}", json=updated_payload)

    assert response.status_code == 200
    assert response.json() == {"id": created_post["id"], **updated_payload}


def test_update_post_missing_returns_404(client, post_payload):
    response = client.put("/posts/999", json=post_payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


def test_update_post_invalid_data_returns_422(client, post_payload):
    created_post = create_post(client, post_payload)

    response = client.put(
        f"/posts/{created_post['id']}",
        json={"title": "", "content": "", "hashtags": [], "approved": False},
    )

    assert response.status_code == 422


def test_delete_post_success(client, post_payload):
    created_post = create_post(client, post_payload)

    response = client.delete(f"/posts/{created_post['id']}")

    assert response.status_code == 204
    assert response.content == b""


def test_delete_post_missing_returns_404(client):
    response = client.delete("/posts/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


def test_post_is_persisted_to_database(client, db_session, post_payload):
    created_post = create_post(client, post_payload)

    db_session.expire_all()
    persisted_post = db_session.get(Post, created_post["id"])

    assert persisted_post is not None
    assert persisted_post.title == post_payload["title"]
    assert persisted_post.content == post_payload["content"]
    assert persisted_post.hashtags == post_payload["hashtags"]
    assert persisted_post.approved is post_payload["approved"]


def test_database_schema_contains_posts_table(db_session):
    inspector = inspect(db_session.bind)

    assert "posts" in inspector.get_table_names()
