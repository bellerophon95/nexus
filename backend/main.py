import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables before any other imports
load_dotenv()
from backend.api import (
    routes_agents,
    routes_documents,
    routes_health,
    routes_history,
    routes_ingest,
    routes_query,
    routes_search,
    routes_skills,
    routes_tasks,
)
from backend.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, version="0.1.0")

# CORS - Explicitly allowing the new AWS domain and keeping legacy Render for compatibility
allowed_origins = [
    "https://project-nexus.duckdns.org",
    "http://project-nexus.duckdns.org",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://.*\.onrender\.com",  # Legacy support
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom Middleware (Disabled temporarily to debug streaming hang)
# app.add_middleware(RequestContextMiddleware)

# Routes
app.include_router(routes_health.router, prefix="/api", tags=["Health"])
app.include_router(routes_ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(routes_search.router, prefix="/api", tags=["Search"])
app.include_router(routes_agents.router, prefix="/api", tags=["Agents"])
app.include_router(routes_query.router, prefix="/api", tags=["Streaming"])
app.include_router(routes_documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(routes_history.router, prefix="/api", tags=["History"])
app.include_router(routes_tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(routes_skills.router, prefix="/api", tags=["Skills"])


@app.on_event("startup")
async def startup_event():
    """
    Nexus Platform Startup: Initialize tracing, validate config, and warm up heavy NLP models.
    """
    print(f"--- {settings.APP_NAME} Startup ---")

    from backend.guardrails.input_guard import warmup_guardrails
    from backend.observability.tracing import init_tracing

    init_tracing()

    # Ensure local storage exists
    os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)

    # Configuration check
    missing = settings.validate_config()
    if missing:
        logger.warning(f"Missing configuration: {', '.join(missing)}")
    else:
        logger.info("All critical configuration variables are present.")

    # Warm up NLP models (Presidio, etc.) in background to avoid blocking health checks
    asyncio.create_task(warmup_guardrails())

    logger.info(f"Nexus Backend started in {settings.ENV} mode (Asynchronous NLP Loading)")


@app.on_event("shutdown")
async def shutdown_event():
    print(f"Shutting down {settings.APP_NAME}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
