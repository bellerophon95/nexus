import logging
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables before any other imports
load_dotenv()
from backend.api import (
    routes_agents,
    routes_documents,
    routes_eval,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Nexus Platform Lifespan Manager: Initializes tracing, config, and background threads.
    """
    print(f"--- {settings.APP_NAME} Startup ---")

    # Diagnostic: Log all registered routes
    for route in app.routes:
        if hasattr(route, "path"):
            logger.info(f"Registered route: {route.path}")

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

    yield  # --- API is active here ---

    # Shutdown logic
    print(f"Shutting down {settings.APP_NAME}")
    from backend.ingestion.worker import get_nlp_executor

    executor = get_nlp_executor()
    executor.shutdown(wait=False, cancel_futures=True)
    logger.info("NLP Process Pool shut down.")


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, version="0.1.0", lifespan=lifespan)

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

# Note: Proxy header trust (X-Forwarded-Proto) is handled by uvicorn's
# --proxy-headers flag (passed in docker-compose.prod.yml and run command).


# Custom Middleware (Disabled temporarily to debug streaming hang)
# app.add_middleware(RequestContextMiddleware)

# 1. Health and System (lowest priority to avoid shadowing)
app.include_router(routes_health.router, prefix="/api", tags=["Health"])

# 2. Functional Domains
app.include_router(routes_ingest.router, prefix="/api/ingest", tags=["Ingestion"])
app.include_router(routes_search.router, prefix="/api/search", tags=["Search"])
app.include_router(routes_agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(routes_query.router, prefix="/api/streaming", tags=["Streaming"])
app.include_router(routes_documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(routes_history.router, prefix="/api/history", tags=["History"])
app.include_router(routes_tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(routes_skills.router, prefix="/api/skills", tags=["Skills"])
app.include_router(routes_eval.router, prefix="/api/evaluation", tags=["Evaluation"])

from fastapi.responses import JSONResponse


@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def custom_404_handler(request: Request, exc: Exception):
    logger.warning(f"404 Not Found Diagnostic: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "path": request.url.path,
            "method": request.method,
            "suggestion": "Check /api/health for registered routes",
        },
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
