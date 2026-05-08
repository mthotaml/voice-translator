import struct
import time
import wave
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import Settings


class LocalStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.media_root = settings.media_root
        self.upload_dir = self.media_root / "uploads"
        self.generated_dir = self.media_root / "generated"

    async def save_temp(self, audio: UploadFile, request_id: str) -> Path:
        suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
        path = self.upload_dir / f"{request_id}{suffix}"
        size = 0
        max_bytes = self.settings.max_audio_mb * 1024 * 1024
        with path.open("wb") as out:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    path.unlink(missing_ok=True)
                    raise ValueError(f"Audio exceeds {self.settings.max_audio_mb} MB limit")
                out.write(chunk)
        return path

    def save_generated_bytes(self, content: bytes, suffix: str = ".mp3") -> str:
        path = self.generated_dir / f"{uuid4()}{suffix}"
        path.write_bytes(content)
        return f"/media/generated/{path.name}"

    def create_demo_audio(self) -> str:
        path = self.generated_dir / f"{uuid4()}.wav"
        sample_rate = 44100
        duration = 0.35
        with wave.open(str(path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for _ in range(int(sample_rate * duration)):
                wav.writeframes(struct.pack("<h", 0))
        return f"/media/generated/{path.name}"

    def cleanup_expired(self) -> int:
        cutoff = time.time() - (self.settings.audio_retention_minutes * 60)
        deleted = 0
        for directory in (self.upload_dir, self.generated_dir):
            for path in directory.glob("*"):
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    deleted += 1
        return deleted
