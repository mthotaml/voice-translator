from app.models import TranslationResult, VoiceProfile
from app.services.translation_provider import DemoTranslationProvider


def test_demo_translation_returns_contract():
    provider = DemoTranslationProvider()
    result = provider.translate_to_hindi(
        "I am really excited to show you how this works.",
        VoiceProfile(duration_seconds=3.0, detected_mood="excited", mood_confidence=0.8),
        None,
    )
    assert isinstance(result, TranslationResult)
    assert result.hindi_translation
    assert result.translation_confidence >= 0.5
