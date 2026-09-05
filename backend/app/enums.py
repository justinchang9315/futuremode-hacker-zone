from enum import IntEnum, StrEnum


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class ASRQuality(StrEnum):
    USABLE = "USABLE"
    UNCERTAIN = "UNCERTAIN"
    NO_SPEECH = "NO_SPEECH"


class AssessmentStatus(StrEnum):
    FINAL = "FINAL"
    PROVISIONAL = "PROVISIONAL"
    NEEDS_RETRY = "NEEDS_RETRY"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Currency(StrEnum):
    COIN = "COIN"
    GEM = "GEM"


class CompanionLevel(IntEnum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class SafetyLevel(IntEnum):
    NORMAL = 0
    EMOTIONAL = 1
    SENSITIVE = 2
    CRITICAL = 3


class ResponseSource(StrEnum):
    BODY_ACTION = "BODY_ACTION"
    APPROVED_TEMPLATE = "APPROVED_TEMPLATE"
    CONSTRAINED_LLM = "CONSTRAINED_LLM"
    SAFETY_OVERRIDE = "SAFETY_OVERRIDE"

