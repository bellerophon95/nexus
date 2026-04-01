import logging
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Explicitly load .env - checking both root and backend directory
env_locations = [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "backend", ".env"),
    ".env",
]
for loc in env_locations:
    if os.path.exists(loc):
        load_dotenv(loc, override=True)
        break
else:
    load_dotenv()  # Fallback


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Nexus AI"
    ENV: str = "development"
    DEBUG: bool = True

    # Supabase Settings
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    # Database Settings
    DATABASE_URL: str | None = None

    # Qdrant Settings
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None

    # Upstash Redis Settings
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None

    # Langfuse Settings
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    # LLM Settings
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # Guardrail Settings
    GUARDRAILS_ENABLED: bool = True
    RESTRICTED_TOPICS: str = "medical,legal,financial,politics"

    # Security/Abuse Prevention (Dormant Mode)
    RATE_LIMIT_PER_MINUTE: int = 20  # Protect against abuse on Free tier

    # Storage Settings
    LOCAL_STORAGE_PATH: str = os.path.join(os.getcwd(), "storage")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def validate_config(self):
        """
        Validates that critical settings are present and not placeholders.
        """
        critical_vars = {
            "SUPABASE_URL": self.SUPABASE_URL,
            "SUPABASE_SERVICE_ROLE_KEY": self.SUPABASE_SERVICE_ROLE_KEY,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
        }

        missing = [k for k, v in critical_vars.items() if not v]
        placeholders = [
            k for k, v in critical_vars.items() if v and ("YOUR_" in v or "INSERT_" in v)
        ]

        if missing:
            msg = f"CRITICAL CONFIG MISSING: {', '.join(missing)}"
            if self.ENV == "production":
                logger.error(msg)
            else:
                logger.warning(msg)

        if placeholders:
            msg = f"PLACEHOLDER DETECTED: {', '.join(placeholders)}"
            logger.error(msg)

        # Additional format check for Supabase Key
        if self.SUPABASE_SERVICE_ROLE_KEY and len(self.SUPABASE_SERVICE_ROLE_KEY) < 20:
            logger.error(
                "SUPABASE_SERVICE_ROLE_KEY is suspiciously short. It should be a long JWT."
            )

        return missing + placeholders


settings = Settings()
