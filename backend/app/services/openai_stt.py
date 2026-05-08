from openai import OpenAI

from app.config import Settings
from app.models import TranscriptionResult


class OpenAISTTProvider:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when DEMO_MODE=false")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        with open(audio_path, "rb") as audio_file:
            result = self.client.audio.transcriptions.create(
                model=self.settings.openai_stt_model,
                file=audio_file,
                language=language.split("-")[0],
            )
        return TranscriptionResult(
            text=result.text,
            confidence=None,
            language_detected=language,
        )
