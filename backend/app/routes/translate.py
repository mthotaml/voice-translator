from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.models import ErrorResponse, VoiceTranslationResponse
from app.services.audio_analysis import AudioAnalyzer
from app.services.elevenlabs_tts import ElevenLabsTTSProvider
from app.services.guardrails import GuardrailService
from app.services.openai_stt import OpenAISTTProvider
from app.services.openai_translation import OpenAITranslationProvider
from app.services.storage import LocalStorage
from app.services.stt_provider import DemoSTTProvider
from app.services.translation_provider import DemoTranslationProvider
from app.services.tts_provider import DemoTTSProvider
from app.services.voice_profile_store import VoiceProfileStore

router = APIRouter(prefix="/api/translate", tags=["translate"])

MOOD_ALIASES = {
    "joy": "joyful",
    "education": "educational",
    "teach": "instructional",
}

SUPPORTED_MOODS = {
    "normal",
    "happy",
    "joyful",
    "excited",
    "angry",
    "sad",
    "calm",
    "serious",
    "instructional",
    "educational",
    "persuasive",
    "urgent",
}


def error_response(request_id: str, status_code: int, reason: str, message: str, guardrails=None):
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            request_id=request_id,
            error="guardrail_blocked" if guardrails else "request_failed",
            reason=reason,
            message=message,
            guardrails=guardrails,
        ).model_dump(),
    )


@router.post("/voice", response_model=VoiceTranslationResponse)
async def translate_voice(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    source_language: str = Form("en-US"),
    target_language: str = Form("hi-IN"),
    mood_override: str | None = Form(None),
    voice_id: str | None = Form(None),
    consent_confirmed: bool = Form(...),
    settings: Settings = Depends(get_settings),
):
    request_id = str(uuid4())
    storage = LocalStorage(settings)
    guardrails = GuardrailService(settings)
    analyzer = AudioAnalyzer(settings)
    selected_voice_id = (voice_id or settings.elevenlabs_voice_id or "").strip()
    selected_mood = normalize_mood_override(mood_override)

    if selected_voice_id.startswith("demo-") and not settings.demo_mode:
        return error_response(
            request_id,
            400,
            "demo_voice_id_selected",
            "A demo voice ID is selected, but the backend is running in real mode. Clear the selected voice ID and paste or enroll a real ElevenLabs voice ID.",
        )

    consent = guardrails.validate_consent(consent_confirmed)
    if not consent.allowed:
        return error_response(
            request_id,
            400,
            "consent_not_confirmed",
            "User consent is required before voice generation.",
            consent,
        )

    try:
        audio_path = await storage.save_temp(audio, request_id)
    except ValueError as exc:
        return error_response(request_id, 413, "audio_too_large", str(exc))

    background_tasks.add_task(storage.cleanup_expired)

    quality = analyzer.validate_audio(audio_path)
    if not quality.allowed:
        return error_response(
            request_id,
            422,
            quality.block_reason or "invalid_audio",
            "Audio file failed validation.",
            quality,
        )

    try:
        stt_provider = DemoSTTProvider() if settings.demo_mode else OpenAISTTProvider(settings)
        translation_provider = DemoTranslationProvider() if settings.demo_mode else OpenAITranslationProvider(settings)
        tts_provider = DemoTTSProvider(storage) if settings.demo_mode else ElevenLabsTTSProvider(settings, storage)

        transcript = stt_provider.transcribe(str(audio_path), source_language)
        content = guardrails.check_content(transcript.text)
        if not content.allowed:
            return error_response(
                request_id,
                400,
                content.block_reason or "unsafe_content",
                "Content safety guardrail blocked this request.",
                content,
            )

        impersonation = guardrails.check_impersonation(transcript.text)
        if not impersonation.allowed:
            return error_response(
                request_id,
                400,
                impersonation.block_reason or "impersonation_risk",
                "Impersonation or fraud risk guardrail blocked this request.",
                impersonation,
            )

        voice_profile = analyzer.extract_features(audio_path, transcript.text)
        if selected_mood:
            voice_profile.detected_mood = selected_mood
            voice_profile.mood_confidence = max(voice_profile.mood_confidence, 0.75)

        translation = translation_provider.translate_to_hindi(
            transcript.text,
            voice_profile,
            selected_mood,
        )

        pii = guardrails.check_pii(transcript.text)
        warnings = analyzer.quality_warnings(
            voice_profile,
            transcript.text,
            translation.translation_confidence,
        )
        if settings.enable_audio_watermark_disclosure:
            warnings.append(
                "Disclosure recommended: this audio was AI-generated as a translated version of an authorized voice sample."
            )

        combined = guardrails.combine(consent, content, impersonation, pii, warnings)

        tts = tts_provider.generate_speech(
            text=translation.hindi_translation,
            style_instructions=translation.tts_style_instructions,
            voice_id=selected_voice_id,
            language_code="hi",
            voice_profile=voice_profile,
        )
        VoiceProfileStore(settings.database_path).mark_used(selected_voice_id)

        return VoiceTranslationResponse(
            request_id=request_id,
            source_language=source_language,
            target_language=target_language,
            english_transcript=transcript.text,
            hindi_translation=translation.hindi_translation,
            detected_mood=voice_profile.detected_mood,
            mood_confidence=voice_profile.mood_confidence,
            voice_profile=voice_profile,
            tts_style_instructions=translation.tts_style_instructions,
            audio_url=tts.audio_url,
            guardrails=combined,
        )
    except Exception as exc:
        message = str(exc)
        status_code = 500
        reason = "provider_error"
        if "Audio file might be corrupted or unsupported" in message:
            status_code = 400
            reason = "unsupported_audio_for_transcription"
            message = (
                "OpenAI could not read this recording format. Try a fresh recording after refreshing the app, "
                "or upload a WAV, MP3, M4A, or MP4 audio file."
            )
        return error_response(request_id, status_code, reason, message)


def normalize_mood_override(mood_override: str | None) -> str | None:
    if not mood_override:
        return None
    mood = mood_override.strip().lower().replace(" ", "_")
    if mood in {"", "auto"}:
        return None
    mood = MOOD_ALIASES.get(mood, mood)
    return mood if mood in SUPPORTED_MOODS else None
