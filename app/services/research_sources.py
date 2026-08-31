"""Pluggable external research-source implementations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from xml.etree import ElementTree

import requests


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
            try:
                published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00")) if published_text else None
            except ValueError:
                published_at = None
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
