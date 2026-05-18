from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.models import VoiceEnrollmentResponse


class ElevenLabsVoiceProvider:
    def __init__(self, settings: Settings):
        if not settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is required when DEMO_MODE=false")
        self.settings = settings

    def enroll_voice(
        self,
        voice_name: str,
        samples: list[tuple[str, bytes, str]],
        description: str | None = None,
    ) -> VoiceEnrollmentResponse:
        if not samples:
            raise ValueError("At least one voice sample is required")

        files = [
            ("files", (filename, content, content_type or "application/octet-stream"))
            for filename, content, content_type in samples
        ]
        data = {
            "name": voice_name,
            "description": description or "Authorized speaker voice clone for VoiceTranslate.",
            "remove_background_noise": "true",
        }
        headers = {"xi-api-key": self.settings.elevenlabs_api_key}

        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()

        payload = response.json()
        return VoiceEnrollmentResponse(
            voice_id=payload["voice_id"],
            voice_name=voice_name,
            provider="elevenlabs",
            created_at=datetime.now(timezone.utc),
            requires_verification=payload.get("requires_verification"),
        )
