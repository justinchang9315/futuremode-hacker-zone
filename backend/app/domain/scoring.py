import unicodedata
from dataclasses import dataclass

from app.config import Settings
from app.enums import ASRQuality, AssessmentStatus


@dataclass(frozen=True)
class AlignmentResult:
    reference_length: int
    transcript_length: int
    matches: int
    substitutions: int
    deletions: int
    insertions: int
    operations: list[dict]


@dataclass(frozen=True)
class AssessmentResult:
    status: AssessmentStatus
    total_score: int | None
    confidence: float
    breakdown: dict[str, int]
    evidence: dict


IGNORED_CATEGORIES = {"Pc", "Pd", "Pe", "Pf", "Pi", "Po", "Ps", "Zl", "Zp", "Zs"}


def normalize_chinese_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and unicodedata.category(char) not in IGNORED_CATEGORIES
    )


def align_text(reference: str, transcript: str) -> AlignmentResult:
    """Levenshtein alignment with auditable character-level operations."""
    ref = normalize_chinese_text(reference)
    hyp = normalize_chinese_text(transcript)
    rows = len(ref) + 1
    cols = len(hyp) + 1
    distance = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        distance[i][0] = i
    for j in range(cols):
        distance[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            substitution_cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            distance[i][j] = min(
                distance[i - 1][j] + 1,
                distance[i][j - 1] + 1,
                distance[i - 1][j - 1] + substitution_cost,
            )

    i, j = len(ref), len(hyp)
    operations: list[dict] = []
    counts = {"MATCH": 0, "SUBSTITUTE": 0, "DELETE": 0, "INSERT": 0}

    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1]:
            operation = {
                "type": "MATCH",
                "reference_index": i - 1,
                "expected": ref[i - 1],
                "actual": hyp[j - 1],
            }
            i -= 1
            j -= 1
        elif (
            i > 0
            and j > 0
            and distance[i][j] == distance[i - 1][j - 1] + 1
        ):
            operation = {
                "type": "SUBSTITUTE",
                "reference_index": i - 1,
                "expected": ref[i - 1],
                "actual": hyp[j - 1],
            }
            i -= 1
            j -= 1
        elif i > 0 and distance[i][j] == distance[i - 1][j] + 1:
            operation = {
                "type": "DELETE",
                "reference_index": i - 1,
                "expected": ref[i - 1],
                "actual": None,
            }
            i -= 1
        else:
            operation = {
                "type": "INSERT",
                "reference_index": i,
                "expected": None,
                "actual": hyp[j - 1],
            }
            j -= 1
        operations.append(operation)
        counts[operation["type"]] += 1

    operations.reverse()
    return AlignmentResult(
        reference_length=len(ref),
        transcript_length=len(hyp),
        matches=counts["MATCH"],
        substitutions=counts["SUBSTITUTE"],
        deletions=counts["DELETE"],
        insertions=counts["INSERT"],
        operations=operations,
    )


def calculate_fluency(duration_ms: int | None, spoken_characters: int) -> tuple[int, str]:
    """Estimate reading pace without claiming pronunciation or emotion analysis."""
    if duration_ms is None or spoken_characters <= 0:
        return 100, "NOT_MEASURED"
    milliseconds_per_character = duration_ms / spoken_characters
    if 300 <= milliseconds_per_character <= 1_200:
        return 100, "PACE_ESTIMATE"
    distance = (
        300 - milliseconds_per_character
        if milliseconds_per_character < 300
        else milliseconds_per_character - 1_200
    )
    return max(40, round(100 - distance / 15)), "PACE_ESTIMATE"


class ReadingScorer:
    ACCURACY_WEIGHT = 0.60
    COMPLETENESS_WEIGHT = 0.25
    FLUENCY_WEIGHT = 0.15

    def __init__(self, settings: Settings):
        self.settings = settings

    def assess(
        self,
        *,
        reference_text: str,
        transcript: str,
        asr_quality: ASRQuality,
        provider_confidence: float | None,
        audio_quality_score: float,
        duration_ms: int | None,
    ) -> AssessmentResult:
        if audio_quality_score < self.settings.min_audio_quality:
            return AssessmentResult(
                status=AssessmentStatus.NEEDS_RETRY,
                total_score=None,
                confidence=round(audio_quality_score, 3),
                breakdown={},
                evidence={"reason": "AUDIO_QUALITY_TOO_LOW"},
            )

        if asr_quality is ASRQuality.NO_SPEECH or not normalize_chinese_text(transcript):
            return AssessmentResult(
                status=AssessmentStatus.NEEDS_RETRY,
                total_score=None,
                confidence=0.0,
                breakdown={},
                evidence={"reason": "NO_SPEECH"},
            )

        if asr_quality is ASRQuality.UNCERTAIN:
            return AssessmentResult(
                status=AssessmentStatus.NEEDS_REVIEW,
                total_score=None,
                confidence=round(provider_confidence or 0.0, 3),
                breakdown={},
                evidence={"reason": "ASR_UNCERTAIN"},
            )

        alignment = align_text(reference_text, transcript)
        if alignment.reference_length == 0:
            return AssessmentResult(
                status=AssessmentStatus.NEEDS_REVIEW,
                total_score=None,
                confidence=0.0,
                breakdown={},
                evidence={"reason": "EMPTY_REFERENCE_TEXT"},
            )

        error_count = alignment.substitutions + alignment.deletions + alignment.insertions
        accuracy = round(max(0.0, 1 - error_count / alignment.reference_length) * 100)
        spoken_reference_chars = alignment.matches + alignment.substitutions
        completeness = round(spoken_reference_chars / alignment.reference_length * 100)
        fluency, fluency_method = calculate_fluency(duration_ms, alignment.transcript_length)
        total = round(
            accuracy * self.ACCURACY_WEIGHT
            + completeness * self.COMPLETENESS_WEIGHT
            + fluency * self.FLUENCY_WEIGHT
        )

        provider_component = provider_confidence if provider_confidence is not None else 0.75
        confidence = round(audio_quality_score * 0.50 + provider_component * 0.50, 3)
        status = (
            AssessmentStatus.FINAL
            if confidence >= self.settings.min_assessment_confidence
            else AssessmentStatus.NEEDS_REVIEW
        )
        score = total if status is AssessmentStatus.FINAL else None
        non_matches = [item for item in alignment.operations if item["type"] != "MATCH"]

        return AssessmentResult(
            status=status,
            total_score=score,
            confidence=confidence,
            breakdown={
                "accuracy": accuracy,
                "completeness": completeness,
                "fluency": fluency,
            },
            evidence={
                "reference_characters": alignment.reference_length,
                "transcript_characters": alignment.transcript_length,
                "matched_characters": alignment.matches,
                "substitutions": alignment.substitutions,
                "deletions": alignment.deletions,
                "insertions": alignment.insertions,
                "uncertain_segments": non_matches[:20],
                "fluency_method": fluency_method,
                "duration_ms": duration_ms,
            },
        )
