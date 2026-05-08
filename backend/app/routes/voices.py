from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.models import ErrorResponse, GuardrailResult, VoiceEnrollmentResponse

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.post("/enroll")
async def enroll_voice(
    audio_samples: list[UploadFile] = File(...),
    voice_name: str = Form(...),
    consent_confirmed: bool = Form(...),
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

    return VoiceEnrollmentResponse(
        voice_id=f"demo-{request_id}",
        voice_name=voice_name,
        provider="demo",
        created_at=datetime.now(timezone.utc),
    )
