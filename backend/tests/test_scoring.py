from app.config import Settings
from app.domain.scoring import ReadingScorer, align_text, normalize_chinese_text
from app.enums import ASRQuality, AssessmentStatus


def test_normalizer_ignores_punctuation_and_spaces() -> None:
    assert normalize_chinese_text("床前 明月光，\n疑是地上霜。") == "床前明月光疑是地上霜"


def test_alignment_exposes_auditable_errors() -> None:
    result = align_text("春眠不覺曉", "春眠覺曉")
    assert result.matches == 4
    assert result.deletions == 1
    assert result.substitutions == 0


def test_perfect_reading_scores_one_hundred() -> None:
    result = ReadingScorer(Settings()).assess(
        reference_text="床前明月光，疑是地上霜。",
        transcript="床前明月光疑是地上霜",
        asr_quality=ASRQuality.USABLE,
        provider_confidence=1.0,
        audio_quality_score=1.0,
        duration_ms=5000,
    )
    assert result.status is AssessmentStatus.FINAL
    assert result.total_score == 100
    assert result.breakdown == {"accuracy": 100, "completeness": 100, "fluency": 100}


def test_low_quality_audio_is_not_scored_or_penalized() -> None:
    result = ReadingScorer(Settings()).assess(
        reference_text="床前明月光",
        transcript="完全不同",
        asr_quality=ASRQuality.USABLE,
        provider_confidence=0.9,
        audio_quality_score=0.2,
        duration_ms=2000,
    )
    assert result.status is AssessmentStatus.NEEDS_RETRY
    assert result.total_score is None
    assert result.evidence["reason"] == "AUDIO_QUALITY_TOO_LOW"
