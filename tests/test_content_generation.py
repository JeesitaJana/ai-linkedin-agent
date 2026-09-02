"""Tests for content generation functionality."""

from datetime import datetime, timezone

import pytest

from app.models.post import Post
from app.models.research_item import ResearchItem
from app.services.content_generation import (
    ContentGenerationError,
    GeneratedContent,
    MockContentGenerator,
    OpenAIContentGenerator,
    generate_post_from_research,
    get_content_generator,
)
from app.services.research_sources import SourceResult


def test_mock_content_generator_generates_valid_content(db_session):
    """Test that the mock content generator produces valid content."""
    generator = MockContentGenerator()
    
    # Create some mock research items
    research_item = ResearchItem(
        topic="artificial intelligence",
        title="New AI Breakthrough",
        summary="Researchers have made significant progress in AI capabilities.",
        source_name="Test Source",
        source_url="https://example.com/ai-breakthrough",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        relevance_score=0.9,
        source_type="research_paper",
        metadata_json={}
    )
    db_session.add(research_item)
    db_session.flush()
    
    content = generator.generate_post([research_item], "artificial intelligence")
    
    assert isinstance(content, GeneratedContent)
    assert content.title
    assert content.content
    assert content.hashtags
    assert content.source_research_item_id == research_item.id
    assert len(content.hashtags) > 0


def test_mock_content_generator_with_empty_research(db_session):
    """Test that mock generator handles empty research gracefully."""
    generator = MockContentGenerator()
    content = generator.generate_post([], "robotics")
    
    assert isinstance(content, GeneratedContent)
    assert content.title
    assert content.content
    assert content.hashtags
    assert content.source_research_item_id is None


def test_generate_post_from_research_creates_unapproved_post(db_session):
    """Test that generated posts are always unapproved."""
    research_item = ResearchItem(
        topic="robotics",
        title="Advanced Robotics Research",
        summary="New developments in robotic automation and control systems.",
        source_name="Robotics Journal",
        source_url="https://example.com/robotics",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        relevance_score=0.85,
        source_type="research_paper",
        metadata_json={}
    )
    db_session.add(research_item)
    db_session.flush()
    
    post = generate_post_from_research(db_session, [research_item], "robotics")
    
    assert isinstance(post, Post)
    assert post.approved is False  # Critical: AI-generated content must not be auto-approved
    assert post.title
    assert post.content
    assert post.hashtags
    assert db_session.get(Post, post.id) is not None


def test_openai_generator_without_api_key_raises_error():
    """Test that OpenAI generator raises error without API key."""
    import os
    # Remove API key if it exists
    original_key = os.environ.get("OPENAI_API_KEY")
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    
    try:
        with pytest.raises(ContentGenerationError, match="OPENAI_API_KEY"):
            OpenAIContentGenerator()
    finally:
        # Restore original key
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key


def test_get_content_generator_returns_mock_by_default():
    """Test that the default content generator is the mock one."""
    import os
    original_generator = os.environ.get("CONTENT_GENERATOR")
    if "CONTENT_GENERATOR" in os.environ:
        del os.environ["CONTENT_GENERATOR"]
    
    try:
        generator = get_content_generator()
        assert isinstance(generator, MockContentGenerator)
    finally:
        if original_generator:
            os.environ["CONTENT_GENERATOR"] = original_generator


def test_get_content_generator_with_openai_config():
    """Test that OpenAI generator is returned when configured."""
    import os
    original_generator = os.environ.get("CONTENT_GENERATOR")
    original_key = os.environ.get("OPENAI_API_KEY")
    
    os.environ["CONTENT_GENERATOR"] = "openai"
    os.environ["OPENAI_API_KEY"] = "test_key"
    
    try:
        generator = get_content_generator()
        assert isinstance(generator, OpenAIContentGenerator)
    finally:
        if original_generator:
            os.environ["CONTENT_GENERATOR"] = original_generator
        else:
            if "CONTENT_GENERATOR" in os.environ:
                del os.environ["CONTENT_GENERATOR"]
        
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        else:
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]


def test_content_generation_error_propagates(db_session):
    """Test that content generation errors are properly propagated."""
    research_item = ResearchItem(
        topic="test",
        title="Test",
        summary="Test summary",
        source_name="Test",
        source_url="https://example.com/test",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        source_type="test",
        metadata_json={}
    )
    db_session.add(research_item)
    db_session.flush()
    
    # Create a generator that always fails
    class FailingGenerator:
        def generate_post(self, research_items, topic):
            raise ContentGenerationError("Generation failed")
    
    # Temporarily replace the generator
    import app.services.content_generation as cg_module
    original_get = cg_module.get_content_generator
    cg_module.get_content_generator = lambda: FailingGenerator()
    
    try:
        with pytest.raises(ContentGenerationError, match="Generation failed"):
            generate_post_from_research(db_session, [research_item], "test")
    finally:
        cg_module.get_content_generator = original_get


def test_hashtag_generation_for_different_topics(db_session):
    """Test that relevant hashtags are generated for different topics."""
    generator = MockContentGenerator()
    
    # Test AI topic
    ai_research = ResearchItem(
        topic="artificial intelligence",
        title="AI Research",
        summary="AI summary",
        source_name="Test",
        source_url="https://example.com/ai",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        relevance_score=0.9,
        source_type="research_paper",
        metadata_json={}
    )
    db_session.add(ai_research)
    db_session.flush()
    
    ai_content = generator.generate_post([ai_research], "artificial intelligence")
    assert "#AI" in ai_content.hashtags or "#artificialintelligence" in ai_content.hashtags
    
    # Test robotics topic
    robotics_research = ResearchItem(
        topic="robotics",
        title="Robotics Research",
        summary="Robotics summary",
        source_name="Test",
        source_url="https://example.com/robotics",
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        relevance_score=0.9,
        source_type="research_paper",
        metadata_json={}
    )
    db_session.add(robotics_research)
    db_session.flush()
    
    robotics_content = generator.generate_post([robotics_research], "robotics")
    assert "#Robotics" in robotics_content.hashtags or "#robotics" in robotics_content.hashtags


def test_generate_post_endpoint_creates_unapproved_post(client, monkeypatch):
    """Test the end-to-end generation route persists a post for GET /posts."""
    from app.api.routes import content_generation as content_route

    class FakeSource:
        def search(self, topic, *, limit=10):
            return [
                SourceResult(
                    title="Robot autonomy advances after new benchmark",
                    summary="Researchers compare humanoid robot learning and safety across real-world trials.",
                    source_url="https://example.com/robotics-benchmark",
                    source_name="Robotics Lab",
                    source_type="research_paper",
                    published_at=datetime.now(timezone.utc),
                    metadata={"provider": "test"},
                )
            ]

    monkeypatch.setattr(content_route, "get_settings", lambda: type("Settings", (), {"research_timeout_seconds": 5, "research_window_days": 30})())
    monkeypatch.setattr(content_route, "get_configured_source", lambda _: [FakeSource()])

    response = client.post("/generate-post", json={"topics": ["robotics", "humanoid robots"], "freshness_days": 30})
    assert response.status_code == 201
    payload = response.json()
    assert payload["approved"] is False
    assert payload["title"]
    assert payload["content"]
    assert payload["hashtags"]

    posts = client.get("/posts")
    assert posts.status_code == 200
    assert any(post["id"] == payload["id"] for post in posts.json())
