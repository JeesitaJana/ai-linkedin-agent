from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.research_item import ResearchItem
from app.services.research import research_topics
from app.services.research_sources import ResearchProviderError, SourceResult


class FakeSource:
    def __init__(self, results): self.results = results
    def search(self, topic, *, limit=10): return self.results.get(topic, [])


def result(title="New AI study", url="https://example.org/1", published_at=None):
    return SourceResult(title, "Useful research summary", url, "Example", "article", published_at, {"kind": "test"})


def test_research_filters_deduplicates_ranks_and_persists(db_session):
    now = datetime.now(timezone.utc)
    source = FakeSource({"AI": [result("AI AI", "https://e.org/1", now), result("AI AI", "https://e.org/1", now), result(None, "https://e.org/no", now)]})
    items = research_topics(db_session, ["AI"], [source], freshness_days=30)
    assert len(items) == 1
    assert items[0].source_url == "https://e.org/1"
    assert db_session.get(ResearchItem, items[0].id) is not None
    assert research_topics(db_session, ["AI"], [source], freshness_days=30)[0].id == items[0].id


def test_research_multiple_topics_and_freshness(db_session):
    source = FakeSource({"AI": [result(url="https://e.org/new", published_at=datetime.now(timezone.utc))], "Health": [result(url="https://e.org/old", published_at=datetime.now(timezone.utc) - timedelta(days=31))]})
    items = research_topics(db_session, ["AI", "Health"], [source], freshness_days=30)
    assert [item.topic for item in items] == ["AI"]


def test_research_request_validation(client):
    assert client.post("/research", json={"topics": []}).status_code == 422
    assert client.post("/research", json={"topics": [" "]}).status_code == 422


def test_research_api_with_mocked_provider(client, monkeypatch):
    from app.api.routes import research as research_route

    monkeypatch.setattr(research_route, "get_settings", lambda: SimpleNamespace(research_timeout_seconds=1, research_window_days=30))
    monkeypatch.setattr(research_route, "get_configured_source", lambda _: [FakeSource({"AI": [result(url="https://e.org/api", published_at=datetime.now(timezone.utc))]})])
    response = client.post("/research", json={"topics": ["AI"]})
    assert response.status_code == 200
    assert response.json()["items"][0]["source_url"] == "https://e.org/api"


def test_provider_failure_is_propagated_without_persistence(db_session):
    """Test that when all sources fail, empty results are returned (graceful degradation)."""
    class FailingSource:
        def search(self, topic, *, limit=10): raise ResearchProviderError("no service")
    items = research_topics(db_session, ["AI"], [FailingSource()], freshness_days=30)
    assert len(items) == 0
    assert db_session.query(ResearchItem).count() == 0


def test_multiple_sources_aggregate_results(db_session):
    """Test that multiple research sources aggregate results correctly."""
    source1 = FakeSource({"AI": [result("AI Study 1", "https://e.org/1", datetime.now(timezone.utc))]})
    source2 = FakeSource({"AI": [result("AI Study 2", "https://e.org/2", datetime.now(timezone.utc))]})
    items = research_topics(db_session, ["AI"], [source1, source2], freshness_days=30)
    assert len(items) == 2
    urls = {item.source_url for item in items}
    assert urls == {"https://e.org/1", "https://e.org/2"}


def test_one_source_failure_doesnt_break_others(db_session):
    """Test that if one source fails, others continue to work."""
    class FailingSource:
        def search(self, topic, *, limit=10): raise ResearchProviderError("service down")
    
    working_source = FakeSource({"AI": [result("AI Study", "https://e.org/working", datetime.now(timezone.utc))]})
    items = research_topics(db_session, ["AI"], [FailingSource(), working_source], freshness_days=30)
    assert len(items) == 1
    assert items[0].source_url == "https://e.org/working"
