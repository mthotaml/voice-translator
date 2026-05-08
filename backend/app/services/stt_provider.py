from typing import Protocol

from app.models import TranscriptionResult


class STTProvider(Protocol):
    def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        ...


class DemoSTTProvider:
    def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        return TranscriptionResult(
            text="I am really excited to show you how this voice translation system works.",
            confidence=0.98,
            language_detected=language,
        )
