from pathlib import Path
import re

from app.config import Settings
from app.models import GuardrailResult, VoiceProfile


TRANSCRIPT_MOOD_CUES: dict[str, tuple[str, ...]] = {
    "urgent": (
        "urgent",
        "immediately",
        "right now",
        "as soon as possible",
        "asap",
        "emergency",
        "quickly",
        "hurry",
        "critical",
    ),
    "angry": (
        "angry",
        "furious",
        "mad",
        "unacceptable",
        "frustrated",
        "outrageous",
        "stop this",
        "i can't believe",
    ),
    "sad": (
        "sad",
        "heartbroken",
        "upset",
        "sorry",
        "lonely",
        "grief",
        "miss you",
        "disappointed",
        "devastated",
    ),
    "joyful": (
        "joy",
        "joyful",
        "celebrate",
        "celebrating",
        "wonderful",
        "fantastic",
        "thrilled",
        "delighted",
    ),
    "excited": (
        "excited",
        "amazing",
        "awesome",
        "can't wait",
        "incredible",
        "super excited",
        "big news",
    ),
    "happy": (
        "happy",
        "glad",
        "pleased",
        "great",
        "good news",
        "thank you",
        "love this",
    ),
    "calm": (
        "calm",
        "relax",
        "slowly",
        "peaceful",
        "steady",
        "take a breath",
        "no rush",
    ),
    "serious": (
        "serious",
        "important",
        "carefully",
        "matter",
        "consequences",
        "responsibility",
        "formal",
    ),
    "instructional": (
        "first",
        "next",
        "then",
        "step",
        "follow",
        "instructions",
        "make sure",
        "remember to",
    ),
    "educational": (
        "explain",
        "learn",
        "understand",
        "concept",
        "example",
        "lesson",
        "because",
        "means that",
    ),
    "persuasive": (
        "believe",
        "should",
        "must",
        "recommend",
        "convince",
        "trust me",
        "the reason",
        "best choice",
    ),
}


class AudioAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate_audio(self, audio_path: Path) -> GuardrailResult:
        warnings: list[str] = []
        if audio_path.stat().st_size > self.settings.max_audio_mb * 1024 * 1024:
            return GuardrailResult(
                allowed=False,
                consent_verified=True,
                content_safe=True,
                impersonation_risk="low",
                block_reason="audio_too_large",
            )
        if audio_path.suffix.lower() not in {".wav", ".webm", ".mp3", ".m4a", ".ogg"}:
            return GuardrailResult(
                allowed=False,
                consent_verified=True,
                content_safe=True,
                impersonation_risk="low",
                block_reason="unsupported_audio_format",
            )
        return GuardrailResult(
            allowed=True,
            consent_verified=True,
            content_safe=True,
            impersonation_risk="low",
            warnings=warnings,
        )

    def extract_features(self, audio_path: Path, transcript: str) -> VoiceProfile:
        try:
            import librosa
            import numpy as np
        except Exception:
            return self._fallback_profile(transcript)

        try:
            y, sr = librosa.load(str(audio_path), sr=None, mono=True)
        except Exception:
            return self._fallback_profile(transcript)

        if y.size == 0:
            return self._fallback_profile(transcript)

        duration = float(librosa.get_duration(y=y, sr=sr))
        rms_frames = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms_energy = float(np.mean(rms_frames))
        peak = float(np.max(np.abs(y)))
        silence_ratio = float(np.mean(rms_frames < max(0.01, rms_energy * 0.35)))
        signal_to_noise = float((np.mean(np.abs(y)) + 1e-8) / (np.std(y - np.mean(y)) + 1e-8))

        f0, _, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        voiced = f0[~np.isnan(f0)] if f0 is not None else np.array([])
        average_pitch = float(np.mean(voiced)) if voiced.size else None
        pitch_range = float(np.max(voiced) - np.min(voiced)) if voiced.size else None
        pitch_std = float(np.std(voiced)) if voiced.size else None

        silent = rms_frames < max(0.01, rms_energy * 0.3)
        pause_lengths = self._contiguous_pause_ms(silent, hop_length=512, sample_rate=sr)
        long_pauses = [pause for pause in pause_lengths if pause > 200]
        speech_rate = self._speech_rate(transcript, duration)
        intensity_variation = float(np.std(rms_frames))

        acoustic_mood, acoustic_confidence = self._classify_mood(
            rms_energy=rms_energy,
            speech_rate=speech_rate or 0,
            pitch_range=pitch_range or 0,
            pitch_std=pitch_std or 0,
            silence_ratio=silence_ratio,
            longest_pause=max(long_pauses, default=0),
            intensity_variation=intensity_variation,
        )
        transcript_mood, transcript_confidence = self._classify_transcript_mood(transcript)
        if transcript_confidence > acoustic_confidence + 0.08:
            mood, confidence = transcript_mood, transcript_confidence
        else:
            mood, confidence = acoustic_mood, acoustic_confidence

        return VoiceProfile(
            duration_seconds=round(duration, 2),
            sample_rate=sr,
            speech_rate_wpm=speech_rate,
            average_pitch_hz=self._round_optional(average_pitch),
            pitch_range_hz=self._round_optional(pitch_range),
            pitch_std_hz=self._round_optional(pitch_std),
            rms_energy=round(rms_energy, 4),
            peak_amplitude=round(peak, 4),
            silence_ratio=round(silence_ratio, 3),
            signal_to_noise_proxy=round(signal_to_noise, 3),
            pause_count=len(long_pauses),
            average_pause_ms=round(float(np.mean(long_pauses)), 1) if long_pauses else 0,
            longest_pause_ms=round(max(long_pauses, default=0), 1),
            intensity_label=self._intensity_label(rms_energy),
            cadence_label=self._cadence_label(speech_rate, long_pauses),
            tone_label=self._tone_label(mood),
            detected_mood=mood,
            mood_confidence=confidence,
        )

    def quality_warnings(self, profile: VoiceProfile, transcript: str, translation_confidence: float = 1.0) -> list[str]:
        warnings = []
        if (profile.silence_ratio or 0) > 0.6:
            warnings.append("Audio contains a lot of silence, so mood detection may be less reliable.")
        if profile.duration_seconds < 2.0:
            warnings.append("Recording is short; use at least a few seconds for better voice and mood analysis.")
        if (profile.signal_to_noise_proxy or 1) < 0.2:
            warnings.append("Background noise may reduce transcription and mood accuracy.")
        if len(transcript.split()) < 3:
            warnings.append("Transcript has very little content.")
        if profile.mood_confidence < 0.4:
            warnings.append("Mood confidence is low.")
        if translation_confidence < 0.5:
            warnings.append("Translation confidence is low.")
        return warnings

    def _fallback_profile(self, transcript: str) -> VoiceProfile:
        word_count = len(transcript.split())
        mood, confidence = self._classify_transcript_mood(transcript)
        return VoiceProfile(
            duration_seconds=max(3.0, word_count / 2.5),
            speech_rate_wpm=140,
            rms_energy=0.05,
            silence_ratio=0.12,
            signal_to_noise_proxy=0.8,
            pause_count=0,
            average_pause_ms=0,
            longest_pause_ms=0,
            intensity_label="medium",
            cadence_label="measured_and_explanatory" if mood in {"educational", "instructional"} else "steady_conversational",
            tone_label=self._tone_label(mood),
            detected_mood=mood,
            mood_confidence=confidence,
        )

    @staticmethod
    def _classify_transcript_mood(transcript: str) -> tuple[str, float]:
        text = f" {transcript.lower()} "
        normalized = re.sub(r"[^a-z0-9' ]+", " ", text)
        scores: dict[str, int] = {}
        for mood, cues in TRANSCRIPT_MOOD_CUES.items():
            score = 0
            for cue in cues:
                cue_text = cue.lower()
                if " " in cue_text:
                    if cue_text in normalized:
                        score += 2
                elif re.search(rf"\b{re.escape(cue_text)}\b", normalized):
                    score += 1
            if score:
                scores[mood] = score

        if not scores:
            return "normal", 0.46

        priority = [
            "urgent",
            "angry",
            "sad",
            "joyful",
            "excited",
            "happy",
            "instructional",
            "educational",
            "persuasive",
            "serious",
            "calm",
        ]
        mood = max(scores, key=lambda item: (scores[item], -priority.index(item)))
        confidence = min(0.82, 0.52 + scores[mood] * 0.08)
        return mood, round(confidence, 2)

    @staticmethod
    def _speech_rate(transcript: str, duration: float) -> float | None:
        if duration <= 0:
            return None
        return round(len(transcript.split()) / duration * 60, 1)

    @staticmethod
    def _contiguous_pause_ms(mask, hop_length: int, sample_rate: int) -> list[float]:
        pauses = []
        current = 0
        for is_silent in mask:
            if is_silent:
                current += 1
            elif current:
                pauses.append(current * hop_length / sample_rate * 1000)
                current = 0
        if current:
            pauses.append(current * hop_length / sample_rate * 1000)
        return pauses

    @staticmethod
    def _classify_mood(
        rms_energy: float,
        speech_rate: float,
        pitch_range: float,
        pitch_std: float,
        silence_ratio: float,
        longest_pause: float,
        intensity_variation: float,
    ) -> tuple[str, float]:
        fast = speech_rate > 155
        slow = speech_rate < 95
        high_energy = rms_energy > 0.07
        low_energy = rms_energy < 0.025
        wide_pitch = pitch_range > 90 or pitch_std > 28
        long_pauses = longest_pause > 700 or silence_ratio > 0.35
        if high_energy and fast and wide_pitch and not long_pauses:
            return "excited", 0.76
        if high_energy and fast and intensity_variation > 0.035:
            return "urgent", 0.7
        if high_energy and wide_pitch and speech_rate > 135:
            return "joyful", 0.68
        if low_energy and slow and long_pauses:
            return "sad", 0.68
        if low_energy and slow:
            return "calm", 0.62
        if low_energy and long_pauses:
            return "serious", 0.56
        if speech_rate and 100 <= speech_rate <= 150 and silence_ratio < 0.28:
            return "educational", 0.64
        if high_energy and wide_pitch:
            return "persuasive", 0.58
        return "normal", 0.52

    @staticmethod
    def _intensity_label(rms_energy: float) -> str:
        if rms_energy > 0.08:
            return "high"
        if rms_energy > 0.045:
            return "medium_high"
        if rms_energy > 0.02:
            return "medium"
        return "low"

    @staticmethod
    def _cadence_label(speech_rate: float | None, pauses: list[float]) -> str:
        if speech_rate and speech_rate > 160:
            return "fast_and_forward"
        if pauses and max(pauses) > 700:
            return "slow_with_long_pauses"
        if speech_rate and 100 <= speech_rate <= 150:
            return "measured_and_explanatory"
        return "steady_conversational"

    @staticmethod
    def _tone_label(mood: str) -> str:
        return {
            "excited": "bright_enthusiastic",
            "joyful": "celebratory",
            "happy": "warm_positive",
            "angry": "sharp_intense",
            "urgent": "focused_urgent",
            "sad": "soft_subdued",
            "calm": "soft_steady",
            "educational": "confident_educational",
            "instructional": "clear_instructional",
            "persuasive": "confident_persuasive",
            "serious": "measured_serious",
        }.get(mood, "neutral_conversational")

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return round(value, 2) if value is not None else None
