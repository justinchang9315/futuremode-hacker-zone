from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.companion import capabilities_for_level
from app.enums import AssessmentStatus
from app.models import (
    CapabilityUnlock,
    ChildProfile,
    PersonalBest,
    ReadingAssessment,
    ReadingAttempt,
    Wallet,
)


@dataclass(frozen=True)
class ProgressionStatus:
    current_level: int
    pending_level: int | None
    completed_contents: int
    mastered_contents: int
    capabilities: list[str]


def _completed_content_count(db: Session, child_id: str) -> int:
    statement = (
        select(func.count(distinct(ReadingAttempt.content_id)))
        .join(
            ReadingAssessment,
            ReadingAssessment.attempt_id == ReadingAttempt.id,
        )
        .where(
            ReadingAttempt.child_id == child_id,
            ReadingAssessment.status == AssessmentStatus.FINAL.value,
        )
    )
    return int(db.scalar(statement) or 0)


def _mastered_content_count(
    db: Session,
    child_id: str,
    settings: Settings,
) -> int:
    statement = (
        select(func.count(distinct(ReadingAttempt.content_id)))
        .join(
            ReadingAssessment,
            ReadingAssessment.attempt_id == ReadingAttempt.id,
        )
        .where(
            ReadingAttempt.child_id == child_id,
            ReadingAssessment.status == AssessmentStatus.FINAL.value,
            ReadingAssessment.total_score >= settings.mastery_score,
            ReadingAssessment.assessment_confidence >= settings.mastery_confidence,
        )
    )
    return int(db.scalar(statement) or 0)


def _record_unlock(db: Session, child_id: str, level: int, guardian_approved: bool) -> None:
    existing = db.scalar(
        select(CapabilityUnlock).where(
            CapabilityUnlock.child_id == child_id,
            CapabilityUnlock.level == level,
        )
    )
    if existing is None:
        db.add(
            CapabilityUnlock(
                child_id=child_id,
                level=level,
                guardian_approved=guardian_approved,
            )
        )


def content_progress(db: Session, child_id: str, settings: Settings) -> tuple[int, int]:
    """Completed/mastered counts without evaluating (or changing) the level."""
    return (
        _completed_content_count(db, child_id),
        _mastered_content_count(db, child_id, settings),
    )


def evaluate_progression(
    db: Session,
    *,
    child: ChildProfile,
    wallet: Wallet,
    settings: Settings,
) -> ProgressionStatus:
    completed = _completed_content_count(db, child.id)
    mastered = _mastered_content_count(db, child.id, settings)

    level_2_eligible = (
        wallet.lifetime_coins >= settings.level_2_lifetime_coins
        and completed >= settings.level_2_completed_contents
    )
    level_3_eligible = (
        level_2_eligible
        and wallet.lifetime_gems >= settings.level_3_lifetime_gems
        and mastered >= settings.level_3_mastered_contents
    )

    if child.current_level < 2 and level_2_eligible:
        child.current_level = 2
        _record_unlock(db, child.id, 2, guardian_approved=False)

    pending_level = None
    if level_3_eligible:
        if child.guardian_approved_level3:
            if child.current_level < 3:
                child.current_level = 3
                _record_unlock(db, child.id, 3, guardian_approved=True)
        elif child.current_level < 3:
            pending_level = 3

    db.flush()
    return ProgressionStatus(
        current_level=child.current_level,
        pending_level=pending_level,
        completed_contents=completed,
        mastered_contents=mastered,
        capabilities=capabilities_for_level(child.current_level),
    )


def get_personal_best(db: Session, child_id: str, content_id: str) -> PersonalBest | None:
    return db.scalar(
        select(PersonalBest).where(
            PersonalBest.child_id == child_id,
            PersonalBest.content_id == content_id,
        )
    )
