from app.config import Settings
from app.models import VoiceProfile
from app.services.elevenlabs_tts import ElevenLabsTTSProvider


class DummyStorage:
    pass


def provider() -> ElevenLabsTTSProvider:
    return ElevenLabsTTSProvider(
        Settings(elevenlabs_api_key="test"),
        DummyStorage(),
    )


def test_fast_excited_profile_uses_expressive_voice_settings():
    settings = provider()._voice_settings_for_profile(
        VoiceProfile(
            duration_seconds=3,
            speech_rate_wpm=175,
            detected_mood="excited",
            mood_confidence=0.8,
        )
    )
    assert settings["stability"] < 0.4
    assert settings["style"] > 0.7


def test_sad_profile_uses_steadier_voice_settings():
    settings = provider()._voice_settings_for_profile(
        VoiceProfile(
            duration_seconds=4,
            speech_rate_wpm=80,
            detected_mood="sad",
            mood_confidence=0.7,
        )
    )
    assert settings["stability"] > 0.6
    assert settings["style"] < 0.3


def test_fast_text_reduces_pause_heavy_punctuation():
    text = provider()._shape_text_for_pace(
        "मैं उत्साहित हूँ, और यह बहुत अच्छा है। चलिए शुरू करते हैं।",
        VoiceProfile(
            duration_seconds=3,
            speech_rate_wpm=170,
            detected_mood="excited",
            mood_confidence=0.8,
        ),
    )
    assert ", " not in text
