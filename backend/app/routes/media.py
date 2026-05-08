from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import Settings, get_settings

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/generated/{filename}")
def download_generated(filename: str, settings: Settings = Depends(get_settings)):
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = settings.media_root / "generated" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    media_type = "audio/mpeg" if Path(filename).suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(path, media_type=media_type, filename=filename)
