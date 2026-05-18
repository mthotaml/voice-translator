from typing import Protocol

from app.models import VoiceEnrollmentResponse


class VoiceProvider(Protocol):
    def enroll_voice(
        self,
        voice_name: str,
        samples: list[tuple[str, bytes, str]],
        description: str | None = None,
    ) -> VoiceEnrollmentResponse:
        ...
