import logging
import os
from langfuse.decorators import observe
from langfuse import Langfuse
from backend.config import settings

# Ensure environment variables are set for the decorators and tools to pick up
os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY or ""
os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY or ""
os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY or ""
os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY or ""

logger = logging.getLogger(__name__)

_langfuse = None

def get_langfuse_client():
    """Returns the initialized Langfuse client, creating it if it doesn't exist."""
    global _langfuse
    if _langfuse is None:
        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL
        )
    return _langfuse

# Export for convenience, but favor get_langfuse_client() for safety
langfuse = None # Placeholder, will be set on first call to get_langfuse_client if needed

def init_tracing():
    """Formally register tracing initialization for startup events."""
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning("Langfuse credentials missing. Tracing may be disabled.")
    else:
        logger.info("Langfuse Tracing initialized.")
    return True

# Export observe decorator for convenience
__all__ = ["observe", "get_langfuse_client", "langfuse", "init_tracing"]
