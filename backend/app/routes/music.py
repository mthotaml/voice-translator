from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.music_library import list_music_tracks

router = APIRouter(prefix="/api/music", tags=["music"])


@router.get("")
def music_tracks(settings: Settings = Depends(get_settings)):
    return list_music_tracks(settings)
