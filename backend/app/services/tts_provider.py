from typing import Protocol

from app.models import TTSResult, VoiceProfile


class TTSProvider(Protocol):
    def generate_speech(
        self,
        text: str,
        style_instructions: str,
        voice_id: str,
        language_code: str,
        voice_profile: VoiceProfile | None = None,
    ) -> TTSResult:
        ...


class DemoTTSProvider:
    def __init__(self, storage):
        self.storage = storage

    def generate_speech(
        self,
        text: str,
        style_instructions: str,
        voice_id: str,
        language_code: str,
        voice_profile: VoiceProfile | None = None,
    ) -> TTSResult:
        audio_url = self.storage.create_demo_audio()
        return TTSResult(audio_url=audio_url, duration_seconds=1.0, provider="demo")
