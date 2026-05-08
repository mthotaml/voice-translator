import httpx

from app.config import Settings
from app.models import TTSResult, VoiceProfile


class ElevenLabsTTSProvider:
    def __init__(self, settings: Settings, storage):
        if not settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is required when DEMO_MODE=false")
        self.settings = settings
        self.storage = storage

    def generate_speech(
        self,
        text: str,
        style_instructions: str,
        voice_id: str,
        language_code: str,
        voice_profile: VoiceProfile | None = None,
    ) -> TTSResult:
        selected_voice_id = voice_id or self.settings.elevenlabs_voice_id
        if not selected_voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID or request voice_id is required")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice_id}"
        payload = {
            "model_id": self.settings.elevenlabs_tts_model,
            # ElevenLabs speaks the `text` field verbatim. Keep style guidance out of
            # the spoken content so generated audio starts with the translation.
            "text": self._shape_text_for_pace(text, voice_profile),
            "voice_settings": self._voice_settings_for_profile(voice_profile),
        }
        headers = {
            "xi-api-key": self.settings.elevenlabs_api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        audio_url = self.storage.save_generated_bytes(response.content, suffix=".mp3")
        return TTSResult(audio_url=audio_url, provider="elevenlabs")

    def _voice_settings_for_profile(self, voice_profile: VoiceProfile | None) -> dict:
        mood = (voice_profile.detected_mood if voice_profile else "normal").lower()
        speech_rate = voice_profile.speech_rate_wpm if voice_profile else None
        fast = (speech_rate or 0) >= 155 or mood in {"excited", "urgent", "joyful", "happy", "angry", "persuasive"}
        slow = (speech_rate or 999) <= 95 or mood in {"sad", "calm", "serious"}

        if fast:
            return {
                "stability": 0.34,
                "similarity_boost": 0.82,
                "style": 0.72,
                "use_speaker_boost": True,
            }
        if slow:
            return {
                "stability": 0.68,
                "similarity_boost": 0.88,
                "style": 0.24,
                "use_speaker_boost": True,
            }
        return {
            "stability": 0.48,
            "similarity_boost": 0.86,
            "style": 0.48,
            "use_speaker_boost": True,
        }

    def _shape_text_for_pace(self, text: str, voice_profile: VoiceProfile | None) -> str:
        mood = (voice_profile.detected_mood if voice_profile else "normal").lower()
        speech_rate = voice_profile.speech_rate_wpm if voice_profile else None
        should_speed_up = (speech_rate or 0) >= 155 or mood in {"excited", "urgent", "joyful", "happy"}
        if not should_speed_up:
            return text

        # Reduce pause-heavy punctuation. This is subtle, but it helps avoid slow,
        # overly careful delivery without adding spoken instructions.
        return (
            text.replace("। ", ". ")
            .replace(", ", " ")
            .replace("—", " ")
            .replace("–", " ")
        )
