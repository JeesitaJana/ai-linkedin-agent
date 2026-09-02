"""Pluggable external research-source implementations."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from xml.etree import ElementTree

import requests


def _coerce_datetime(value: str | datetime | int | float | None) -> datetime | None:
    """Normalize provider timestamps into timezone-aware UTC datetimes."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

    for candidate in dict.fromkeys(candidates):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(candidate)
            except (TypeError, ValueError, IndexError):
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


class ResearchProviderError(Exception):
    """External provider failure safe to expose as an application error."""


@dataclass(frozen=True)
class SourceResult:
    title: str | None
    summary: str | None
    source_url: str | None
    source_name: str
    source_type: str
    published_at: datetime | None = None
    metadata: dict[str, object] | None = None


class ResearchSource(Protocol):
    def search(self, topic: str, *, limit: int = 10) -> list[SourceResult]: ...


class ArxivResearchSource:
    """Small, respectful client for arXiv's public Atom search API."""

    endpoint = "https://export.arxiv.org/api/query"
    atom_namespace = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, timeout_seconds: float = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def search(self, topic: str, *, limit: int = 10) -> list[SourceResult]:
        try:
            response = requests.get(
                self.endpoint,
                params={"search_query": f'all:"{topic}"', "start": 0, "max_results": limit},
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ai-linkedin-content-agent/0.1 (research only)"},
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (requests.RequestException, ElementTree.ParseError) as exc:
            raise ResearchProviderError("Research provider is unavailable") from exc

        results: list[SourceResult] = []
        for entry in root.findall("atom:entry", self.atom_namespace):
            published_text = entry.findtext("atom:published", default="", namespaces=self.atom_namespace)
            published_at = _coerce_datetime(published_text)
            results.append(SourceResult(
                title=entry.findtext("atom:title", default="", namespaces=self.atom_namespace).strip() or None,
                summary=entry.findtext("atom:summary", default="", namespaces=self.atom_namespace).strip() or None,
                source_url=entry.findtext("atom:id", default="", namespaces=self.atom_namespace).strip() or None,
                source_name="arXiv",
                source_type="research_paper",
                published_at=published_at,
                metadata={"provider": "arxiv"},
            ))
        return results


class NewsAPISource:
    """Research source using NewsAPI for technology news and articles."""

    endpoint = "https://newsapi.org/v2/everything"

    def __init__(self, timeout_seconds: float = 10) -> None:
        self.timeout_seconds = timeout_seconds
        self.api_key = os.getenv("NEWSAPI_API_KEY")
        if not self.api_key:
            raise ResearchProviderError("NEWSAPI_API_KEY environment variable is not set")

    def search(self, topic: str, *, limit: int = 10) -> list[SourceResult]:
        try:
            params = {
                "q": topic,
                "apiKey": self.api_key,
                "pageSize": limit,
                "sortBy": "publishedAt",
                "language": "en",
            }
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ai-linkedin-content-agent/0.1 (research only)"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise ResearchProviderError(f"NewsAPI error: {data.get('message', 'Unknown error')}")

            articles = data.get("articles")
            if not isinstance(articles, list):
                return []

            results: list[SourceResult] = []
            for article in articles:
                published_at = _coerce_datetime(article.get("publishedAt"))
                results.append(SourceResult(
                    title=article.get("title"),
                    summary=article.get("description"),
                    source_url=article.get("url"),
                    source_name=article.get("source", {}).get("name", "NewsAPI"),
                    source_type="news",
                    published_at=published_at,
                    metadata={"provider": "newsapi", "author": article.get("author")},
                ))
            return results

        except requests.RequestException as exc:
            raise ResearchProviderError("NewsAPI service is unavailable") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ResearchProviderError("NewsAPI response parsing failed") from exc


class HackerNewsSource:
    """Research source using the official Algolia-powered Hacker News search API."""

    endpoint = "https://hn.algolia.com/api/v1/search"

    def __init__(self, timeout_seconds: float = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def search(self, topic: str, *, limit: int = 10) -> list[SourceResult]:
        try:
            response = requests.get(
                self.endpoint,
                params={
                    "query": topic,
                    "hitsPerPage": min(max(limit, 1), 50),
                    "tags": "story",
                },
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ai-linkedin-content-agent/0.1 (research only)"},
            )
            response.raise_for_status()
            data = response.json()

            hits = data.get("hits")
            if not isinstance(hits, list):
                return []

            results: list[SourceResult] = []
            for hit in hits[:limit]:
                title = (hit.get("title") or "").strip()
                if not title:
                    continue
                source_url = (hit.get("url") or hit.get("story_url") or "").strip() or None
                published_at = _coerce_datetime(hit.get("created_at"))
                results.append(SourceResult(
                    title=title,
                    summary=(hit.get("story_text") or hit.get("title") or source_url or "").strip() or title,
                    source_url=source_url,
                    source_name="Hacker News",
                    source_type="tech_news",
                    published_at=published_at,
                    metadata={"provider": "hackernews", "points": hit.get("points"), "author": hit.get("author")},
                ))
            return results

        except requests.RequestException as exc:
            raise ResearchProviderError("Hacker News API is unavailable") from exc
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ResearchProviderError("Hacker News response parsing failed") from exc


class TechCrunchSource:
    """Research source using TechCrunch RSS feed for technology news."""

    endpoint = "https://techcrunch.com/feed/"

    def __init__(self, timeout_seconds: float = 10) -> None:
        self.timeout_seconds = timeout_seconds
        self.rss_namespace = {"rss": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}

    def search(self, topic: str, *, limit: int = 10) -> list[SourceResult]:
        try:
            response = requests.get(
                self.endpoint,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ai-linkedin-content-agent/0.1 (research only)"},
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)

            results: list[SourceResult] = []
            topic_lower = topic.lower()

            for item in root.iter("item"):
                title = (item.findtext("title", default="") or "").strip()
                description = (item.findtext("description", default="") or "").strip()
                link = (item.findtext("link", default="") or "").strip()

                if not title:
                    continue
                if topic_lower not in title.lower() and topic_lower not in description.lower():
                    continue

                published_at = _coerce_datetime(item.findtext("pubDate", default=""))
                results.append(SourceResult(
                    title=title,
                    summary=description or title,
                    source_url=link or None,
                    source_name="TechCrunch",
                    source_type="tech_news",
                    published_at=published_at,
                    metadata={"provider": "techcrunch"},
                ))

                if len(results) >= limit:
                    break

            return results

        except requests.RequestException as exc:
            raise ResearchProviderError("TechCrunch RSS feed is unavailable") from exc
        except ElementTree.ParseError as exc:
            raise ResearchProviderError("TechCrunch RSS parsing failed") from exc
