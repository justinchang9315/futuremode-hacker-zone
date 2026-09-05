from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    CapabilityUnlock,
    ChildProfile,
    ContentItem,
    DialogueTurn,
    FeedbackEvent,
    GuardianConsent,
    ModelRun,
    PersonalBest,
    ReadingAssessment,
    ReadingAttempt,
    ReadingSession,
    RewardItemOwnership,
    RewardTransaction,
    SafetyEvent,
    Wallet,
)
from app.schemas import SessionSummary


def get_session_summary(db: Session, session_id: str) -> SessionSummary:
    session = db.get(ReadingSession, session_id)
    assert session is not None
    rows = list(
        db.execute(
            select(ReadingAssessment.total_score, ContentItem.title)
            .join(ReadingAttempt, ReadingAssessment.attempt_id == ReadingAttempt.id)
            .join(ContentItem, ReadingAttempt.content_id == ContentItem.id)
            .where(ReadingAttempt.session_id == session_id)
        )
    )
    scores = [row.total_score for row in rows if row.total_score is not None]
    titles = list(dict.fromkeys(row.title for row in rows))
    currencies = dict(
        db.execute(
            select(RewardTransaction.currency, func.coalesce(func.sum(RewardTransaction.amount), 0))
            .join(
                ReadingAssessment,
                RewardTransaction.assessment_id == ReadingAssessment.id,
            )
            .join(ReadingAttempt, ReadingAssessment.attempt_id == ReadingAttempt.id)
            .where(ReadingAttempt.session_id == session_id, RewardTransaction.amount > 0)
            .group_by(RewardTransaction.currency)
        ).all()
    )
    safety_count = db.scalar(
        select(func.count(SafetyEvent.id)).where(SafetyEvent.session_id == session_id)
    ) or 0
    return SessionSummary(
        session_id=session.id,
        child_id=session.child_id,
        status=session.status,
        completed_attempts=len(scores),
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
        earned_coins=int(currencies.get("COIN", 0)),
        earned_gems=int(currencies.get("GEM", 0)),
        safety_events=safety_count,
        content_titles=titles,
        guardian_prompt="可以請孩子說說今天教機器人的內容，以及下次想再練習哪一段。",
    )


def delete_child_data(db: Session, child_id: str) -> None:
    attempt_ids = select(ReadingAttempt.id).where(ReadingAttempt.child_id == child_id)
    assessment_ids = select(ReadingAssessment.id).where(
        ReadingAssessment.attempt_id.in_(attempt_ids)
    )
    db.execute(delete(FeedbackEvent).where(FeedbackEvent.child_id == child_id))
    db.execute(delete(ModelRun).where(ModelRun.child_id == child_id))
    db.execute(delete(SafetyEvent).where(SafetyEvent.child_id == child_id))
    db.execute(delete(DialogueTurn).where(DialogueTurn.child_id == child_id))
    db.execute(delete(RewardItemOwnership).where(RewardItemOwnership.child_id == child_id))
    db.execute(delete(CapabilityUnlock).where(CapabilityUnlock.child_id == child_id))
    db.execute(delete(RewardTransaction).where(RewardTransaction.child_id == child_id))
    db.execute(delete(PersonalBest).where(PersonalBest.child_id == child_id))
    db.execute(delete(ReadingAssessment).where(ReadingAssessment.id.in_(assessment_ids)))
    db.execute(delete(ReadingAttempt).where(ReadingAttempt.child_id == child_id))
    db.execute(delete(ReadingSession).where(ReadingSession.child_id == child_id))
    db.execute(delete(GuardianConsent).where(GuardianConsent.child_id == child_id))
    db.execute(delete(Wallet).where(Wallet.child_id == child_id))
    db.execute(delete(ChildProfile).where(ChildProfile.id == child_id))
    db.commit()
