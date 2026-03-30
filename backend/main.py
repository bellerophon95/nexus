from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import asyncio
from typing import Optional

# Load environment variables before any other imports
load_dotenv()
from backend.config import settings
from backend.api import routes_health, routes_ingest, routes_search, routes_agents, routes_query, routes_documents, routes_history, routes_tasks
from backend.api.middleware import RequestContextMiddleware

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
    print(f"--- {settings.APP_NAME} Startup ---")
    print(f"Environment: {settings.ENV}")
    print(f"Debug Mode: {settings.DEBUG}")
    
    # Check for missing critical configuration
    missing = settings.validate_config()
    if missing:
        print(f"WARNING: Missing critical variables: {', '.join(missing)}")
        print("The application may fail during RAG operations.")
    else:
        print("All critical configuration variables are present.")
        
    # Masked diagnostic info for Render logs
    def mask(val: Optional[str]) -> str:
        return f"{val[:6]}...{val[-4:]}" if val and len(val) > 10 else "MISSING"
    
    print(f"SUPABASE_URL: {'SET' if settings.SUPABASE_URL else 'MISSING'} ({mask(settings.SUPABASE_URL)})")
    print(f"OPENAI_API_KEY: {'SET' if settings.OPENAI_API_KEY else 'MISSING'}")
    print("--------------------------------")

    # Warm up guardrail models in background to prevent first-request hang
    from backend.guardrails.input_guard import warmup_guardrails
    loop = asyncio.get_running_loop()
    loop.create_task(warmup_guardrails())

@app.on_event("shutdown")
async def shutdown_event():
    print(f"Shutting down {settings.APP_NAME}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
