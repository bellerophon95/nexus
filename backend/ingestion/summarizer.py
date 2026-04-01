import logging

from openai import OpenAI

from backend.config import settings
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Use sync client for pipeline worker compat
client = OpenAI(api_key=settings.OPENAI_API_KEY)


@observe(name="Generate Document Description")
def generate_summary(text: str) -> str:
    """
    Generates a 1-2 sentence professional summary of document text.
    Used for filtering and library overview.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set. Skipping summary.")
        return ""

    if not text or len(text.strip()) < 50:
        return "Short or empty document content."

    try:
        # We only need the first few thousand characters for a good summary
        sample_text = text[:8000]

        system_prompt = (
            "You are a professional documentation assistant. "
            "Write a concise, high-level, 1-2 sentence description of the following document. "
            "Focus on the main topic and purpose. "
            "Do NOT use 'This document is about...' or quotes. "
            "Example: 'Contains detailed technical specifications and deployment guides for the Nexus AI infrastructure.'"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Snippet:\n\n{sample_text}"},
            ],
            max_tokens=60,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to generate document summary: {e}")
        return ""
