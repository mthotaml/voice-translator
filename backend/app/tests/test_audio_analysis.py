from pathlib import Path

from app.config import Settings
from app.services.audio_analysis import AudioAnalyzer


def test_audio_validator_rejects_unsupported_format(tmp_path: Path):
    path = tmp_path / "clip.txt"
    path.write_text("not audio")
    result = AudioAnalyzer(Settings()).validate_audio(path)
    assert result.allowed is False
    assert result.block_reason == "unsupported_audio_format"


def test_fallback_profile_detects_excited_transcript():
    profile = AudioAnalyzer(Settings())._fallback_profile("I am excited about this great demo")
    assert profile.detected_mood == "excited"
    assert 0 < profile.mood_confidence < 1


def test_transcript_mood_classifier_covers_supported_moods():
    analyzer = AudioAnalyzer(Settings())
    examples = {
        "urgent": "This is urgent, please do it immediately right now.",
        "angry": "I am angry and frustrated because this is unacceptable.",
        "sad": "I am sad and heartbroken, I really miss you.",
        "joyful": "We are celebrating this wonderful joyful moment.",
        "happy": "I am happy and glad to share good news.",
        "calm": "Stay calm, relax, and take a breath.",
        "serious": "This is a serious and important matter.",
        "instructional": "First follow this step, then make sure you save it.",
        "educational": "Let me explain this concept with an example.",
        "persuasive": "I believe this is the best choice and you should trust me.",
    }
    for expected, transcript in examples.items():
        mood, confidence = analyzer._classify_transcript_mood(transcript)
        assert mood == expected
        assert confidence > 0.5
