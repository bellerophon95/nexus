from datetime import datetime

from fastapi import APIRouter, Request

from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    # Diagnostic: Extract all registered routes from the app
    routes = []
    for r in request.app.routes:
        if hasattr(r, "path"):
            routes.append(f"{list(r.methods) if hasattr(r, 'methods') else '[]'} {r.path}")

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat(),
        "registered_routes": sorted(routes),
    }
