from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import campaigns, health, media, music, translate, voices

settings = get_settings()

app = FastAPI(
    title="Pure Green Hyperlocal Video API",
    version="0.1.0",
    description="Mock-first campaign generation API for localized wellness video marketing.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(health.router)
app.include_router(media.router)
app.include_router(music.router)
app.include_router(translate.router)
app.include_router(voices.router)
app.include_router(campaigns.router)
