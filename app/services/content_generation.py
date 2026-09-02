"""AI-powered LinkedIn content generation service."""

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.post import Post
from app.models.research_item import ResearchItem
from app.schemas.posts import PostCreate


class ContentGenerationError(Exception):
   """Content generation failure safe to expose as an application error."""


class LinkedInDraft(BaseModel):
   """Validated AI output contract for generated LinkedIn drafts."""

   title: str = Field(..., min_length=1, max_length=200)
   content: str = Field(..., min_length=1, max_length=3000)
   hashtags: list[str] = Field(..., min_length=1, max_length=10)

   @field_validator("hashtags")
   @classmethod
   def validate_hashtags(cls, value: list[str]) -> list[str]:
       cleaned: list[str] = []
       for tag in value:
           normalized = re.sub(r"[^#A-Za-z0-9_]", "", str(tag).strip())
           if not normalized:
               continue
           if not normalized.startswith("#"):
               normalized = f"#{normalized}"
           cleaned.append(normalized[:30])
       if not cleaned:
           raise ValueError("At least one hashtag is required")
       return cleaned[:10]


@dataclass(frozen=True)
class GeneratedContent:
   """Structure for AI-generated content."""

   title: str
   content: str
   hashtags: list[str]
   source_research_item_id: int | None = None

   @classmethod
   def from_validated(cls, payload: LinkedInDraft, source_research_item_id: int | None = None) -> "GeneratedContent":
       return cls(
           title=payload.title.strip(),
           content=payload.content.strip(),
           hashtags=[tag.strip() for tag in payload.hashtags],
           source_research_item_id=source_research_item_id,
       )


class ContentGenerator(Protocol):
   """Protocol for content generation implementations."""

   def generate_post(
       self,
       research_items: list[ResearchItem],
       topic: str,
       instructions: str | None = None,
   ) -> GeneratedContent:
       """Generate a LinkedIn post from research items."""
       ...


def _normalize_topic(topic: str | None, research_items: list[ResearchItem]) -> str:
   if topic and topic.strip():
       return topic.strip()
   if research_items:
       return research_items[0].topic.strip()
   return "technology"


def _build_research_context(research_items: list[ResearchItem], limit: int = 5) -> str:
   if not research_items:
       return "No research items available."

   context_lines: list[str] = []
   for index, item in enumerate(research_items[:limit], start=1):
       summary = (item.summary or "").strip()
       if len(summary) > 260:
           summary = summary[:257].rstrip() + "..."
       context_lines.append(
           f"{index}. Title: {item.title}\n"
           f"   Source: {item.source_name}\n"
           f"   Summary: {summary}\n"
       )
   return "\n".join(context_lines)


def _sanitize_ai_output(data: Any, fallback_topic: str, research_items: list[ResearchItem]) -> GeneratedContent:
   if isinstance(data, dict):
       payload = {
           "title": str(data.get("title") or "").strip(),
           "content": str(data.get("content") or "").strip(),
           "hashtags": data.get("hashtags") or [],
       }
   else:
       payload = {"title": "", "content": str(data or "").strip(), "hashtags": []}

   if not payload["title"]:
       payload["title"] = f"Insights on {fallback_topic.title()}"
   if not payload["content"]:
       payload["content"] = (
           f"Recent developments in {fallback_topic} point to meaningful change. "
           f"The strongest trend is that better research and technology are increasingly converging around practical impact.\n\n"
           "This is a good moment to look closely at the signals, test ideas, and think about what this means for teams, customers, and the broader ecosystem."
       )

   draft = LinkedInDraft.model_validate(payload)
   return GeneratedContent.from_validated(
       draft,
       source_research_item_id=research_items[0].id if research_items else None,
   )


class OpenAIContentGenerator:
   """Content generator using OpenAI GPT models."""

   def __init__(self) -> None:
       self.api_key = os.getenv("OPENAI_API_KEY")
       if not self.api_key:
           raise ContentGenerationError("OPENAI_API_KEY environment variable is not set")
       self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

   def generate_post(
       self,
       research_items: list[ResearchItem],
       topic: str,
       instructions: str | None = None,
   ) -> GeneratedContent:
       """Generate a LinkedIn post using OpenAI."""
       try:
           import openai

           client = openai.OpenAI(api_key=self.api_key)
           context = _build_research_context(research_items)
           prompt = self._build_prompt(topic, context, instructions)

           response = client.chat.completions.create(
               model=self.model,
               messages=[
                   {
                       "role": "system",
                       "content": (
                           "You are a senior technology writer creating professional LinkedIn posts. "
                           "Use only the research context provided. Do not invent facts or claims that are not present. "
                           "Write a strong hook, practical insight, concise structure, and relevant hashtags."
                       ),
                   },
                   {"role": "user", "content": prompt},
               ],
               temperature=0.7,
               max_tokens=1000,
           )

           content = response.choices[0].message.content
           if not content:
               raise ContentGenerationError("OpenAI returned empty content")

           parsed = self._parse_response(content)
           if not parsed:
               raise ContentGenerationError("OpenAI returned malformed content")

           fallback_topic = _normalize_topic(topic, research_items)
           return _sanitize_ai_output(parsed, fallback_topic, research_items)

       except ImportError:
           raise ContentGenerationError("OpenAI package not installed. Install with: pip install openai")
       except Exception as exc:
           raise ContentGenerationError(f"OpenAI content generation failed: {exc}") from exc

   def _build_prompt(self, topic: str, research_context: str, instructions: str | None = None) -> str:
       instruction_block = f"\nExtra guidance: {instructions.strip()}\n" if instructions and instructions.strip() else ""
       return f"""
Generate a professional LinkedIn post about: {topic}

Use only the research context below. Do not invent facts, numbers, or quotes.
If the information is incomplete, be careful and communicate uncertainty without adding unsupported details.

Research context:
{research_context}
{instruction_block}

Return valid JSON with exactly these keys:
{
 "title": "A compelling LinkedIn post title",
 "content": "The full post body in plain text. Use readable paragraphs and a clear conclusion or question.",
 "hashtags": ["#RelevantTag1", "#RelevantTag2", "#RelevantTag3"]
}

Rules:
- Use a strong opening that feels professional and relevant to a LinkedIn audience.
- Explain what matters, why it matters, and what to watch next.
- Keep the post concise but thoughtful.
- Include 3-6 hashtags.
- Avoid emojis and generic filler.
"""

   def _parse_response(self, content: str) -> Any:
       cleaned = content.strip()
       if not cleaned:
           return None
       try:
           return json.loads(cleaned)
       except json.JSONDecodeError:
           title_match = re.search(r"TITLE\s*:\s*(.+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
           content_match = re.search(r"CONTENT\s*:\s*(.+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
           hashtags_match = re.search(r"HASHTAGS\s*:\s*(.+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
           if not (title_match and content_match):
               return None
           tag_values = []
           if hashtags_match:
               tag_values = [tag.strip() for tag in hashtags_match.group(1).split(",") if tag.strip()]
           return {
               "title": title_match.group(1).strip(),
               "content": content_match.group(1).strip(),
               "hashtags": tag_values,
           }


class MockContentGenerator:
   """Mock content generator for testing without AI API."""

   def generate_post(
       self,
       research_items: list[ResearchItem],
       topic: str,
       instructions: str | None = None,
   ) -> GeneratedContent:
       """Generate a mock LinkedIn post from research items."""
       topic_name = _normalize_topic(topic, research_items)
       if not research_items:
           return GeneratedContent(
               title=f"Latest developments in {topic_name}",
               content=(
                   f"Exciting things are happening in the world of {topic_name}. "
                   "A new wave of research and product momentum is shaping the conversation.\n\n"
                   "What are your thoughts on where this trend is heading next?"
               ),
               hashtags=_build_hashtags(topic_name),
           )

       top_item = research_items[0]
       hook = top_item.title
       if len(hook) > 60:
           hook = hook[:57].rstrip() + "..."
       intro = top_item.summary.strip() if top_item.summary else "Recent research is showing strong momentum in this area."
       if len(intro) > 240:
           intro = intro[:237].rstrip() + "..."

       content = (
           f"{intro}\n\n"
           f"This development is especially relevant for {topic_name}, because it highlights how quickly teams are moving from experimentation to real-world deployment.\n\n"
           f"The strongest signal is that practical systems are becoming more capable, and the conversation is shifting from novelty to operational impact.\n\n"
           f"Source: {top_item.source_name}\n\n"
           "What do you think this means for teams building the next generation of products and systems?"
       )

       return GeneratedContent(
           title=f"Exploring {hook}",
           content=content,
           hashtags=_build_hashtags(topic_name),
           source_research_item_id=top_item.id,
       )


def _build_hashtags(topic: str) -> list[str]:
   base_topic = re.sub(r"[^A-Za-z0-9 ]", "", topic).strip()
   tags = ["#Technology", "#Innovation"]
   if base_topic:
       tags.insert(0, f"#{base_topic.replace(' ', '')}")
   if "ai" in topic.lower() or "artificial" in topic.lower():
       tags.append("#AI")
   if "robot" in topic.lower():
       tags.append("#Robotics")
   unique: list[str] = []
   for tag in tags:
       if tag not in unique:
           unique.append(tag)
   return unique[:5]


def get_content_generator() -> ContentGenerator:
   """Factory function to get the configured content generator."""
   provider = os.getenv("CONTENT_GENERATOR")
   if provider == "mock":
       return MockContentGenerator()
   if provider == "openai":
       if not os.getenv("OPENAI_API_KEY"):
           return MockContentGenerator()
       return OpenAIContentGenerator()
   if os.getenv("OPENAI_API_KEY"):
       return OpenAIContentGenerator()
   return MockContentGenerator()


class ContentGenerationService:
   """Service for orchestrating content generation from research items."""

   def __init__(self, generator: ContentGenerator | None = None) -> None:
       self.generator = generator or get_content_generator()

   def generate(self, research_items: list[ResearchItem], topic: str, instructions: str | None = None) -> GeneratedContent:
       if not research_items:
           raise ContentGenerationError("No research items available for content generation")
       try:
           try:
               return self.generator.generate_post(research_items, topic, instructions=instructions)
           except TypeError as exc:
               if "instructions" not in str(exc):
                   raise
               return self.generator.generate_post(research_items, topic)
       except ContentGenerationError:
           raise
       except Exception as exc:
           raise ContentGenerationError(f"Content generation failed: {exc}") from exc


def generate_post_from_research(
   db: Session,
   research_items: list[ResearchItem],
   topic: str,
   instructions: str | None = None,
) -> Post:
   """Generate and save a LinkedIn post from research items."""
   service = ContentGenerationService()

   try:
       generated = service.generate(research_items, topic, instructions=instructions)

       post_data = PostCreate(
           title=generated.title,
           content=generated.content,
           hashtags=generated.hashtags,
           approved=False,
       )

       post = Post(
           title=post_data.title,
           content=post_data.content,
           hashtags=post_data.hashtags,
           approved=post_data.approved,
       )

       db.add(post)
       db.flush()
       db.refresh(post)
       return post

   except ContentGenerationError:
       raise
   except ValidationError as exc:
       raise ContentGenerationError(f"Generated content is invalid: {exc}") from exc
   except Exception as exc:
       raise ContentGenerationError(f"Post generation failed: {exc}") from exc


__all__ = [
   "ContentGenerationError",
   "ContentGenerator",
   "ContentGenerationService",
   "GeneratedContent",
   "LinkedInDraft",
   "OpenAIContentGenerator",
   "MockContentGenerator",
   "get_content_generator",
   "generate_post_from_research",
]
