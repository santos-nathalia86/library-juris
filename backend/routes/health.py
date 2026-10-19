from fastapi import APIRouter, Depends

from core.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["sistema"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "max_upload_mb": settings.max_upload_mb}
