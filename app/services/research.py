"""Research normalization, quality filtering, ranking, and persistence."""

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_item import ResearchItem
from app.services.research_sources import (
    ArxivResearchSource,
    HackerNewsSource,
    NewsAPISource,
    ResearchProviderError,
    ResearchSource,
    SourceResult,
    TechCrunchSource,
)


def get_configured_source(timeout_seconds: float) -> list[ResearchSource]:
    """Returns a list of configured research sources based on environment variables."""
    sources = []
    provider = os.getenv("RESEARCH_PROVIDER", "arxiv")
    
    if provider == "arxiv":
        sources.append(ArxivResearchSource(timeout_seconds=timeout_seconds))
    elif provider == "newsapi":
        sources.append(NewsAPISource(timeout_seconds=timeout_seconds))
    elif provider == "hackernews":
        sources.append(HackerNewsSource(timeout_seconds=timeout_seconds))
    elif provider == "techcrunch":
        sources.append(TechCrunchSource(timeout_seconds=timeout_seconds))
    elif provider == "all":
        # Use all available sources (note: NewsAPI requires API key)
        sources.append(ArxivResearchSource(timeout_seconds=timeout_seconds))
        sources.append(HackerNewsSource(timeout_seconds=timeout_seconds))
        sources.append(TechCrunchSource(timeout_seconds=timeout_seconds))
        if os.getenv("NEWSAPI_API_KEY"):
            sources.append(NewsAPISource(timeout_seconds=timeout_seconds))
    else:
        # Default to arxiv
        sources.append(ArxivResearchSource(timeout_seconds=timeout_seconds))
    
    return sources


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
        "discovered_at": datetime.now(timezone.utc),
        "relevance_score": _score(topic, title, summary, result.source_type, result.published_at),
        "source_type": result.source_type.strip() or "unknown",
        "metadata_json": result.metadata or {},
    }


def _score(topic: str, title: str, summary: str, source_type: str = "unknown", published_at: datetime | None = None) -> float:
    """Improved relevance scoring considering multiple factors."""
    topic_lower = topic.casefold()
    text = f"{title} {summary}".casefold()
    
    # Base score from keyword matches
    keyword_score = 0.0
    keyword_count = text.count(topic_lower)
    
    # Score based on keyword frequency
    if keyword_count > 0:
        keyword_score = min(0.4, 0.1 * keyword_count)
    
    # Bonus for topic appearing in title (higher weight)
    if topic_lower in title.casefold():
        keyword_score += 0.2
    
    # Source quality score
    source_quality_scores = {
        "research_paper": 0.3,  # Academic papers
        "tech_news": 0.25,      # Tech news sources
        "news": 0.2,           # General news
        "unknown": 0.1,        # Unknown sources
    }
    source_score = source_quality_scores.get(source_type, 0.1)
    
    # Recency score (if publication date is available)
    recency_score = 0.0
    if published_at:
        days_old = (datetime.now(timezone.utc) - published_at).days
        if days_old <= 7:
            recency_score = 0.2
        elif days_old <= 30:
            recency_score = 0.15
        elif days_old <= 90:
            recency_score = 0.1
        elif days_old <= 180:
            recency_score = 0.05
    
    # Completeness score (check if we have all required fields)
    completeness_score = 0.0
    if title and summary:
        completeness_score = 0.1
    
    # Combine all scores
    total_score = keyword_score + source_score + recency_score + completeness_score
    
    # Normalize to 0-1 range
    return min(1.0, total_score)


def research_topics(
    db: Session,
    topics: list[str],
    sources: list[ResearchSource],
    *,
    freshness_days: int | None,
) -> list[ResearchItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days) if freshness_days else None
    accepted: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    
    for topic in topics:
        for source in sources:
            try:
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
            except ResearchProviderError:
                # Continue with other sources if one fails
                continue

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
