from typing import Protocol

from app.models import TranslationResult, VoiceProfile


class TranslationProvider(Protocol):
    def translate_to_hindi(
        self,
        english_transcript: str,
        voice_profile: VoiceProfile,
        mood_override: str | None,
    ) -> TranslationResult:
        ...


class DemoTranslationProvider:
    def translate_to_hindi(
        self,
        english_transcript: str,
        voice_profile: VoiceProfile,
        mood_override: str | None,
    ) -> TranslationResult:
        mood = mood_override or voice_profile.detected_mood
        return TranslationResult(
            hindi_translation="मैं आपको यह दिखाने के लिए बहुत उत्साहित हूँ कि यह voice translation system कैसे काम करता है।",
            style_summary=f"Natural spoken Hindi with {mood} energy.",
            tts_style_instructions=(
                "Speak in the user's cloned voice with an excited, clear, warm tone. "
                "Keep a medium-fast pace, natural Hindi pronunciation, and preserve the speaker's enthusiasm."
            ),
            translation_confidence=0.93,
        )
