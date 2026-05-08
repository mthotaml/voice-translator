from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {"status": "ok", "version": "0.1.0", "demo_mode": settings.demo_mode}
