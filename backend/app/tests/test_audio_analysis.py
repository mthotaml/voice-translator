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
