from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import health, media, translate, voices

settings = get_settings()

app = FastAPI(
    title="VoiceTranslate API",
    version="0.1.0",
    description="Emotion-preserving English to Hindi voice translator.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(health.router)
app.include_router(media.router)
app.include_router(translate.router)
app.include_router(voices.router)
