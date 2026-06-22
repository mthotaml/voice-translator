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
    requires_verification: bool | None = None


class SpeakerVoiceProfile(BaseModel):
    id: int
    voice_id: str
    voice_name: str
    provider: str
    description: str | None = None
    consent_confirmed: bool
    created_at: datetime
    last_used_at: datetime | None = None


TargetAudience = str
ProductFocus = str
VideoFormat = str
CampaignTone = str


class CampaignCreate(BaseModel):
    businessName: str = "Pure Green"
    locationName: str | None = None
    neighborhood: str | None = None
    goal: str | None = None
    targetAudience: list[TargetAudience] = Field(default_factory=lambda: ["gym_goers", "runners"])
    videoLengthSeconds: int = 30
    format: VideoFormat = "vertical_9_16"
    tone: CampaignTone = "energetic"
    productFocus: list[ProductFocus] = Field(default_factory=lambda: ["smoothies", "acai_bowls"])
    cta: str | None = None
    musicStyle: str = "Upbeat wellness pop"
    voiceId: str | None = None
    narrationScript: str | None = None


class PolishNarrationRequest(BaseModel):
    roughText: str
    businessName: str = "Pure Green"
    locationName: str | None = None
    neighborhood: str | None = None
    targetAudience: list[TargetAudience] = Field(default_factory=list)
    productFocus: list[ProductFocus] = Field(default_factory=list)
    tone: CampaignTone = "energetic"
    cta: str | None = None
    videoLengthSeconds: int = 30


class PolishNarrationResponse(BaseModel):
    polishedNarration: str
    hook: str
    onScreenText: list[str] = Field(default_factory=list)
    rationale: str
    provider: str = "demo"


class AutoCampaignCreate(CampaignCreate):
    folderPath: str | None = None


class MediaAnalysis(BaseModel):
    detectedObjects: list[str] = Field(default_factory=list)
    detectedFoods: list[str] = Field(default_factory=list)
    setting: str = ""
    mood: str = ""
    vibe: str = ""
    lighting: str = "good"
    backgroundDescription: str = ""
    localContextSignals: list[str] = Field(default_factory=list)
    fitnessSignals: list[str] = Field(default_factory=list)
    wellnessSignals: list[str] = Field(default_factory=list)
    brandSafetyFlags: list[str] = Field(default_factory=list)
    qualityScore: int = 0
    recommendedUse: str = "b_roll"
    suggestedCaptionText: str = ""


class CampaignAsset(BaseModel):
    id: str
    campaignId: str
    type: str
    url: str
    filename: str
    width: int | None = None
    height: int | None = None
    orientation: str = "unknown"
    formatFit: list[str] = Field(default_factory=list)
    skipReason: str | None = None
    durationSeconds: float | None = None
    analysis: MediaAnalysis | None = None
    qualityScore: int | None = None
    createdAt: str


class Scene(BaseModel):
    index: int
    startTime: float
    endTime: float
    assetIds: list[str] = Field(default_factory=list)
    visualDirection: str
    onScreenText: str
    voiceoverLine: str
    transition: str = "cut"


class Caption(BaseModel):
    startTime: float
    endTime: float
    text: str


class CampaignBrief(BaseModel):
    campaignAngle: str
    targetAudienceSummary: str
    primaryMessage: str
    secondaryMessages: list[str] = Field(default_factory=list)
    visualStrategy: str
    hookOptions: list[str] = Field(default_factory=list)
    ctaOptions: list[str] = Field(default_factory=list)
    riskNotes: list[str] = Field(default_factory=list)


class Storyboard(BaseModel):
    campaignId: str
    totalDurationSeconds: int
    scenes: list[Scene]
    voiceoverScript: str
    captions: list[Caption]
    musicStyle: str
    voiceTone: str = "Warm, conversational wellness narrator"
    voiceRecommendation: str = "Use a clear, friendly voice with natural pacing."
    musicRationale: str = "Selected to match the campaign tone and visual energy."
    complianceNotes: list[str] = Field(default_factory=list)
    cta: str
    qualityScore: int = 86


class ComplianceResult(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    rewrittenScript: str
    rewrittenCaptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SocialCaption(BaseModel):
    shortCaption: str
    longerCaption: str
    hashtags: list[str]


class MusicTrack(BaseModel):
    id: str
    title: str
    file: str
    energy: str = "balanced"
    bpm: int | None = None
    mood: list[str] = Field(default_factory=list)
    license: str = "owned_or_licensed"
    defaultVolume: float = 0.1
    duckedVolume: float = 0.035
    matchTheme: str | None = None
    matchReason: str | None = None


class Campaign(BaseModel):
    id: str
    name: str
    locationName: str | None = None
    neighborhood: str | None = None
    businessName: str
    goal: str | None = None
    targetAudience: list[TargetAudience]
    videoLengthSeconds: int
    format: VideoFormat
    tone: CampaignTone
    productFocus: list[ProductFocus]
    cta: str | None = None
    status: str = "draft"
    musicStyle: str = "Upbeat wellness pop"
    voiceId: str | None = None
    narrationScript: str | None = None
    createdAt: str
    updatedAt: str
    assets: list[CampaignAsset] = Field(default_factory=list)
    brief: CampaignBrief | None = None
    storyboard: Storyboard | None = None
    compliance: ComplianceResult | None = None
    socialCaption: SocialCaption | None = None
    musicTrack: MusicTrack | None = None
    narrationUrl: str | None = None
    renderUrl: str | None = None
