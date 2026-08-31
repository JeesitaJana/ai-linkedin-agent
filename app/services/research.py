"""Research normalization, quality filtering, ranking, and persistence."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_item import ResearchItem
from app.services.research_sources import ArxivResearchSource, ResearchProviderError, ResearchSource, SourceResult


def get_configured_source(timeout_seconds: float) -> ResearchSource:
    return ArxivResearchSource(timeout_seconds=timeout_seconds)


def _normalize(topic: str, result: SourceResult) -> dict[str, object] | None:
    title = (result.title or "").strip()
    summary = " ".join((result.summary or "").split())
    url = (result.source_url or "").strip()
    if not title or not summary or not url:
        return None
    return {
        "topic": topic,
        "title": title,
        "summary": summary,
        "source_name": result.source_name.strip() or "Unknown",
        "source_url": url,
        "published_at": result.published_at,
        "discovered_at": datetime.now(UTC),
        "relevance_score": _score(topic, title, summary),
        "source_type": result.source_type.strip() or "unknown",
        "metadata_json": result.metadata or {},
    }


def _score(topic: str, title: str, summary: str) -> float:
    """Deterministic keyword score, deliberately simple until an LLM phase exists."""
    text = f"{title} {summary}".casefold()
    return min(1.0, 0.5 + (0.25 * text.count(topic.casefold())))


def research_topics(
    db: Session,
    topics: list[str],
    source: ResearchSource,
    *,
    freshness_days: int | None,
) -> list[ResearchItem]:
    cutoff = datetime.now(UTC) - timedelta(days=freshness_days) if freshness_days else None
    accepted: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for topic in topics:
        for raw_result in source.search(topic):
            item = _normalize(topic, raw_result)
            if item is None:
                continue
            published_at = item["published_at"]
            if cutoff and (published_at is None or published_at < cutoff):
                continue
            url = str(item["source_url"])
            title = str(item["title"]).casefold()
            if url in seen_urls or title in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(title)
            accepted.append(item)

    accepted.sort(key=lambda item: float(item["relevance_score"] or 0), reverse=True)
    persisted: list[ResearchItem] = []
    for item in accepted:
        existing = db.scalar(select(ResearchItem).where(ResearchItem.source_url == item["source_url"]))
        if existing:
            persisted.append(existing)
            continue
        model = ResearchItem(**item)  # type: ignore[arg-type]
        db.add(model)
        db.flush()
        db.refresh(model)
        persisted.append(model)
    return persisted


__all__ = ["ResearchProviderError", "get_configured_source", "research_topics"]
