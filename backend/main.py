import asyncio
import logging
import os
import threading

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

from starlette.middleware.proxy_headers import ProxyHeadersMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://.*\.onrender\.com",  # Legacy support
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trust proxy headers (e.g. X-Forwarded-Proto) from Caddy
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


# Custom Middleware (Disabled temporarily to debug streaming hang)
# app.add_middleware(RequestContextMiddleware)

# Routes
app.include_router(routes_health.router, prefix="/api", tags=["Health"])
app.include_router(routes_ingest.router, prefix="/api/ingest", tags=["Ingestion"])
app.include_router(routes_search.router, prefix="/api/search", tags=["Search"])
app.include_router(routes_agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(routes_query.router, prefix="/api/streaming", tags=["Streaming"])
app.include_router(routes_documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(routes_history.router, prefix="/api/history", tags=["History"])
app.include_router(routes_tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(routes_skills.router, prefix="/api/skills", tags=["Skills"])


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

    # 2. Start Background Ingestion Worker & Reaper in dedicated threads
    from backend.ingestion.reaper import run_reaper_loop
    from backend.ingestion.worker import run_worker_thread

    t1 = threading.Thread(target=run_worker_thread, daemon=True)
    t1.start()

    t2 = threading.Thread(target=run_reaper_loop, daemon=True)
    t2.start()

    logger.info(
        f"Nexus Backend started in {settings.ENV} mode (Dedicated Ingestion Worker & Reaper Threads)"
    )


@app.on_event("shutdown")
async def shutdown_event():
    print(f"Shutting down {settings.APP_NAME}")
    # Clean shutdown of the NLP executor
    from backend.ingestion.worker import get_nlp_executor

    executor = get_nlp_executor()
    executor.shutdown(wait=False, cancel_futures=True)
    logger.info("NLP Process Pool shut down.")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
