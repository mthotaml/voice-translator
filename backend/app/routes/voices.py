from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.models import ErrorResponse, GuardrailResult, SpeakerVoiceProfile, VoiceEnrollmentResponse
from app.services.elevenlabs_voice import ElevenLabsVoiceProvider
from app.services.voice_profile_store import VoiceProfileStore

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("", response_model=list[SpeakerVoiceProfile])
def list_voices(settings: Settings = Depends(get_settings)):
    store = VoiceProfileStore(settings.database_path)
    return store.list_profiles()


@router.post("/enroll")
async def enroll_voice(
    audio_samples: list[UploadFile] = File(...),
    voice_name: str = Form(...),
    consent_confirmed: bool = Form(...),
    description: str | None = Form(None),
    settings: Settings = Depends(get_settings),
):
    request_id = str(uuid4())
    if not consent_confirmed:
        guardrails = GuardrailResult(
            allowed=False,
            consent_verified=False,
            content_safe=True,
            impersonation_risk="low",
            block_reason="consent_not_confirmed",
        )
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                request_id=request_id,
                error="guardrail_blocked",
                reason="consent_not_confirmed",
                message="User consent is required before voice enrollment.",
                guardrails=guardrails,
            ).model_dump(),
        )

    if settings.demo_mode:
        response = VoiceEnrollmentResponse(
            voice_id=f"demo-{request_id}",
            voice_name=voice_name,
            provider="demo",
            created_at=datetime.now(timezone.utc),
            requires_verification=False,
        )
        VoiceProfileStore(settings.database_path).upsert_profile(
            voice_id=response.voice_id,
            voice_name=response.voice_name,
            provider=response.provider,
            description=description,
            consent_confirmed=consent_confirmed,
        )
        return response

    try:
        samples = [
            (
                sample.filename or f"sample-{index}.webm",
                await sample.read(),
                sample.content_type or "application/octet-stream",
            )
            for index, sample in enumerate(audio_samples)
        ]
        provider = ElevenLabsVoiceProvider(settings)
        response = provider.enroll_voice(voice_name, samples, description)
        VoiceProfileStore(settings.database_path).upsert_profile(
            voice_id=response.voice_id,
            voice_name=response.voice_name,
            provider=response.provider,
            description=description,
            consent_confirmed=consent_confirmed,
        )
        return response
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        reason = "provider_error"
        message = str(exc)
        if status_code == 401:
            reason = "elevenlabs_unauthorized"
            message = (
                "ElevenLabs rejected the API key. Check ELEVENLABS_API_KEY in .env, "
                "make sure it is active, and restart the backend."
            )
        elif status_code == 403:
            reason = "elevenlabs_forbidden"
            message = (
                "ElevenLabs refused this voice creation request. Check whether your plan/API key "
                "has permission for voice cloning."
            )
        elif status_code == 400:
            reason = "elevenlabs_bad_request"
            message = (
                "ElevenLabs could not create the voice from these samples. Try cleaner audio, "
                "a supported format, or a longer single-speaker sample."
            )
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                request_id=request_id,
                error="voice_enrollment_failed",
                reason=reason,
                message=message,
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                request_id=request_id,
                error="voice_enrollment_failed",
                reason="provider_error",
                message=str(exc),
            ).model_dump(),
        )
