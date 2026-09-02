"""AI-powered LinkedIn content generation service."""

import os
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.research_item import ResearchItem
from app.schemas.posts import PostCreate


class ContentGenerationError(Exception):
    """Content generation failure safe to expose as an application error."""


@dataclass(frozen=True)
class GeneratedContent:
    """Structure for AI-generated content."""
    title: str
    content: str
    hashtags: list[str]
    source_research_item_id: int | None = None


class ContentGenerator(Protocol):
    """Protocol for content generation implementations."""
    
    def generate_post(self, research_items: list[ResearchItem], topic: str) -> GeneratedContent:
        """Generate a LinkedIn post from research items."""
        ...


class OpenAIContentGenerator:
    """Content generator using OpenAI GPT models."""
    
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ContentGenerationError("OPENAI_API_KEY environment variable is not set")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
    
    def generate_post(self, research_items: list[ResearchItem], topic: str) -> GeneratedContent:
        """Generate a LinkedIn post using OpenAI."""
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            # Prepare context from research items
            research_context = self._prepare_research_context(research_items)
            
            prompt = self._build_prompt(topic, research_context)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert LinkedIn content creator specializing in technology and innovation. Create engaging, professional posts that are informative and shareable."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ContentGenerationError("OpenAI returned empty content")
            
            return self._parse_generated_content(content, research_items)
            
        except ImportError:
            raise ContentGenerationError("OpenAI package not installed. Install with: pip install openai")
        except Exception as exc:
            raise ContentGenerationError(f"OpenAI content generation failed: {str(exc)}") from exc
    
    def _prepare_research_context(self, research_items: list[ResearchItem]) -> str:
        """Prepare research items as context for the AI."""
        context = "Recent research and news:\n\n"
        for item in research_items[:5]:  # Limit to top 5 items
            context += f"- {item.title}\n"
            context += f"  {item.summary[:200]}...\n"
            context += f"  Source: {item.source_name}\n\n"
        return context
    
    def _build_prompt(self, topic: str, research_context: str) -> str:
        """Build the prompt for content generation."""
        return f"""
Create a LinkedIn post about {topic} based on the following research:

{research_context}

Requirements:
1. Write a compelling, professional post that would engage a LinkedIn audience
2. Include a catchy title
3. Make it informative but concise (under 1000 characters for the main content)
4. End with a question or call to action to encourage engagement
5. Suggest 3-5 relevant hashtags

Format your response as:
TITLE: [your title]
CONTENT: [your post content]
HASHTAGS: [comma-separated hashtags]
"""
    
    def _parse_generated_content(self, content: str, research_items: list[ResearchItem]) -> GeneratedContent:
        """Parse the AI-generated content into structured format."""
        title = ""
        post_content = ""
        hashtags = []
        
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
                current_section = "title"
            elif line.startswith("CONTENT:"):
                post_content = line.replace("CONTENT:", "").strip()
                current_section = "content"
            elif line.startswith("HASHTAGS:"):
                hashtags_str = line.replace("HASHTAGS:", "").strip()
                hashtags = [tag.strip() for tag in hashtags_str.split(",")]
                current_section = "hashtags"
            elif current_section == "content" and line:
                post_content += " " + line
        
        # Fallback if parsing failed
        if not title:
            title = f"Insights on {research_items[0].topic if research_items else 'Technology'}"
        if not post_content:
            post_content = content
        if not hashtags:
            hashtags = ["#technology", "#innovation"]
        
        # Get the most relevant research item ID
        source_id = research_items[0].id if research_items else None
        
        return GeneratedContent(
            title=title,
            content=post_content.strip(),
            hashtags=hashtags,
            source_research_item_id=source_id
        )


class MockContentGenerator:
    """Mock content generator for testing without AI API."""
    
    def generate_post(self, research_items: list[ResearchItem], topic: str) -> GeneratedContent:
        """Generate a mock LinkedIn post from research items."""
        if not research_items:
            return GeneratedContent(
                title=f"Latest developments in {topic}",
                content=f"Exciting things are happening in the world of {topic}. Stay tuned for more updates! 🚀\n\nWhat are your thoughts on the future of {topic}?",
                hashtags=[f"#{topic.replace(' ', '')}", "#innovation", "#technology"]
            )
        
        # Use the top research item
        top_item = research_items[0]
        
        title = f"Exploring {top_item.title[:50]}..."
        content = f"{top_item.summary}\n\nThis development in {topic} is quite significant. What do you think about this trend? 🤔\n\nSource: {top_item.source_name}"
        
        # Generate relevant hashtags
        hashtags = [f"#{topic.replace(' ', '')}", "#innovation", "#technology"]
        if "AI" in topic or "artificial intelligence" in topic.lower():
            hashtags.append("#AI")
        if "robotics" in topic.lower():
            hashtags.append("#Robotics")
        
        return GeneratedContent(
            title=title,
            content=content,
            hashtags=hashtags,
            source_research_item_id=top_item.id
        )


def get_content_generator() -> ContentGenerator:
    """Factory function to get the configured content generator."""
    provider = os.getenv("CONTENT_GENERATOR", "mock")
    
    if provider == "openai":
        return OpenAIContentGenerator()
    else:
        return MockContentGenerator()


def generate_post_from_research(
    db: Session,
    research_items: list[ResearchItem],
    topic: str,
) -> Post:
    """Generate and save a LinkedIn post from research items."""
    generator = get_content_generator()
    
    try:
        generated = generator.generate_post(research_items, topic)
        
        post_data = PostCreate(
            title=generated.title,
            content=generated.content,
            hashtags=generated.hashtags,
            approved=False  # Always false for AI-generated content
        )
        
        post = Post(
            title=post_data.title,
            content=post_data.content,
            hashtags=post_data.hashtags,
            approved=post_data.approved
        )
        
        db.add(post)
        db.flush()
        db.refresh(post)
        
        return post
        
    except ContentGenerationError as exc:
        raise exc
    except Exception as exc:
        raise ContentGenerationError(f"Post generation failed: {str(exc)}") from exc


__all__ = [
    "ContentGenerationError",
    "ContentGenerator", 
    "GeneratedContent",
    "OpenAIContentGenerator",
    "MockContentGenerator",
    "get_content_generator",
    "generate_post_from_research"
]
