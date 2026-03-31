from datetime import datetime

from fastapi import APIRouter

from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat(),
    }
