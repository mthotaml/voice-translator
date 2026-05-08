import json
from pathlib import Path

from openai import OpenAI

from app.config import Settings
from app.models import TranslationResult, VoiceProfile


class OpenAITranslationProvider:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when DEMO_MODE=false")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.prompt_template = Path("app/prompts/translation_prompt.md").read_text(encoding="utf-8")

    def translate_to_hindi(
        self,
        english_transcript: str,
        voice_profile: VoiceProfile,
        mood_override: str | None,
    ) -> TranslationResult:
        profile_summary = voice_profile.model_dump_json()
        prompt = (
            self.prompt_template
            .replace("{{english_transcript}}", english_transcript)
            .replace("{{detected_mood}}", voice_profile.detected_mood)
            .replace("{{mood_confidence}}", str(voice_profile.mood_confidence))
            .replace("{{voice_profile_summary}}", profile_summary)
            .replace("{{mood_override}}", mood_override or "None")
        )
        response = self.client.chat.completions.create(
            model=self.settings.openai_translation_model,
            messages=[
                {"role": "system", "content": "Return only strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return TranslationResult(**data)
