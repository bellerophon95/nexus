from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import asyncio
import logging
from typing import Optional

# Load environment variables before any other imports
load_dotenv()
from backend.config import settings
from backend.api import routes_health, routes_ingest, routes_search, routes_agents, routes_query, routes_documents, routes_history, routes_tasks
from backend.api.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="0.1.0"
)

# CORS - Explicit origins required when allow_credentials=True
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://35.16.25.121:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

@app.on_event("startup")
async def startup_event():
    """
    Consolidated startup: Initialize tracing, validate config, and set storage.
    Heavy ML models are lazy-loaded on first request for 512MB RAM compatibility.
    """
    print(f"--- {settings.APP_NAME} Startup ---")
    
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
        
    logger.info(f"Nexus Backend started in {settings.ENV} mode (Plan: Free Tier Optimized)")

@app.on_event("shutdown")
async def shutdown_event():
    print(f"Shutting down {settings.APP_NAME}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
