from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional, List
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

# Explicitly load .env - checking both root and backend directory
env_locations = [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "backend", ".env"),
    ".env"
]
for loc in env_locations:
    if os.path.exists(loc):
        load_dotenv(loc, override=True)
        break
else:
    load_dotenv() # Fallback

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Project Nexus"
    ENV: str = "development"
    DEBUG: bool = True
    
    # Supabase Settings
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    # Database Settings
    DATABASE_URL: Optional[str] = None
    
    # Qdrant Settings
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    
    # Upstash Redis Settings
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None
    
    # Langfuse Settings
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    
    # LLM Settings
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Guardrail Settings
    GUARDRAILS_ENABLED: bool = True
    RESTRICTED_TOPICS: str = "medical,legal,financial,politics"
    
    # Security/Abuse Prevention (Dormant Mode)
    RATE_LIMIT_PER_MINUTE: int = 20 # Protect against abuse on Free tier
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_config(self):
        """
        Validates that critical settings are present, especially in production.
        Identifies missing secrets that will cause runtime failures.
        """
        critical_vars = {
            "SUPABASE_URL": self.SUPABASE_URL,
            "SUPABASE_SERVICE_ROLE_KEY": self.SUPABASE_SERVICE_ROLE_KEY,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
        }
        
        missing = [k for k, v in critical_vars.items() if not v]
        
        if missing:
            msg = f"CRITICAL CONFIG MISSING: {', '.join(missing)}"
            if self.ENV == "production":
                logger.error(msg)
                # We don't raise here to allow the app to start and serve a health check
                # so the user can see the logs on Render.
            else:
                logger.warning(msg)
        else:
            logger.info("Critical configuration validated successfully.")
            
        return missing

settings = Settings()
