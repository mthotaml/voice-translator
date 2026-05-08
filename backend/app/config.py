from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    backend_port: int = 8000
    max_audio_seconds: int = 120
    max_audio_mb: int = 25
    enable_local_file_storage: bool = True
    audio_retention_minutes: int = 60
    demo_mode: bool = True

    openai_api_key: str = ""
    openai_stt_model: str = "gpt-4o-transcribe"
    openai_translation_model: str = "gpt-4.1-mini"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_128"

    require_voice_consent: bool = True
    block_impersonation: bool = True
    enable_content_moderation: bool = True
    enable_audio_watermark_disclosure: bool = True

    media_root: Path = Field(default=Path("media"))

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    (settings.media_root / "uploads").mkdir(exist_ok=True)
    (settings.media_root / "generated").mkdir(exist_ok=True)
    return settings
