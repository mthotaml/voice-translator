from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VoiceProfile(BaseModel):
    duration_seconds: float
    sample_rate: int | None = None
    speech_rate_wpm: float | None = None
    average_pitch_hz: float | None = None
    pitch_range_hz: float | None = None
    pitch_std_hz: float | None = None
    rms_energy: float | None = None
    peak_amplitude: float | None = None
    silence_ratio: float | None = None
    signal_to_noise_proxy: float | None = None
    pause_count: int | None = None
    average_pause_ms: float | None = None
    longest_pause_ms: float | None = None
    intensity_label: str = "unknown"
    cadence_label: str = "unknown"
    tone_label: str = "unknown"
    detected_mood: str = "normal"
    mood_confidence: float = 0.0


class GuardrailResult(BaseModel):
    allowed: bool
    consent_verified: bool
    content_safe: bool
    impersonation_risk: str
    pii_detected: bool = False
    warnings: list[str] = Field(default_factory=list)
    block_reason: str | None = None


class TranscriptionResult(BaseModel):
    text: str
    confidence: float | None = None
    language_detected: str | None = None


class TranslationResult(BaseModel):
    hindi_translation: str
    style_summary: str
    tts_style_instructions: str
    translation_confidence: float


class TTSResult(BaseModel):
    audio_url: str | None = None
    audio_base64: str | None = None
    duration_seconds: float | None = None
    provider: str


class VoiceTranslationResponse(BaseModel):
    request_id: str
    source_language: str
    target_language: str
    english_transcript: str
    hindi_translation: str
    detected_mood: str
    mood_confidence: float
    voice_profile: VoiceProfile
    tts_style_instructions: str
    audio_url: str | None = None
    guardrails: GuardrailResult


class ErrorResponse(BaseModel):
    request_id: str
    error: str
    reason: str
    message: str
    guardrails: GuardrailResult | None = None


class VoiceEnrollmentResponse(BaseModel):
    voice_id: str
    voice_name: str
    provider: str
    created_at: datetime
