from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings, get_settings
from app.domain.rewards import get_or_create_wallet
from app.exceptions import ForbiddenError, NotFoundError
from app.models import CapabilityUnlock, ChildProfile, GuardianConsent, ReadingSession
from app.schemas import SessionCreate, SessionRead


def create_session(db: Session, request: SessionCreate, settings: Settings) -> SessionRead:
    if not request.guardian_present:
        raise ForbiddenError("Phase I Demo 需要家長或照顧者在場並同意後才能開始。")
    if not request.guardian_acknowledged_ai or not request.guardian_acknowledged_privacy:
        raise ForbiddenError("請家長先確認 AI 身分、資料使用方式與陪同責任。")

    display_name = (request.display_name or "").strip() or None
    if request.child_id:
        child = db.get(ChildProfile, request.child_id)
        if child is None:
            raise NotFoundError("找不到指定的孩童設定。")
        # 同一個孩子改暱稱時直接更新，不要另外開一個 profile，否則進度會歸零。
        if display_name and child.display_name != display_name:
            child.display_name = display_name
    else:
        child = ChildProfile(
            display_name=display_name,
            age=request.age,
            grade_level=request.grade_level,
        )
        db.add(child)
        db.flush()

    consent = GuardianConsent(
        child_id=child.id,
        consent_version=request.consent_version,
        guardian_present=True,
    )
    db.add(consent)
    db.flush()

    session = ReadingSession(
        child_id=child.id,
        guardian_consent_id=consent.id,
        status="ACTIVE",
    )
    db.add(session)
    get_or_create_wallet(db, child.id)
    level_one = db.scalar(
        select(CapabilityUnlock).where(
            CapabilityUnlock.child_id == child.id,
            CapabilityUnlock.level == 1,
        )
    )
    if level_one is None:
        db.add(CapabilityUnlock(child_id=child.id, level=1, guardian_approved=True))
    db.commit()
    session_token, token_expires_at = create_access_token(
        session_id=session.id,
        child_id=child.id,
        role="session",
        settings=settings,
    )
    guardian_token, _ = create_access_token(
        session_id=session.id,
        child_id=child.id,
        role="guardian",
        settings=settings,
    )
    return SessionRead(
        id=session.id,
        child_id=child.id,
        display_name=child.display_name,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        current_level=child.current_level,
        session_token=session_token,
        guardian_token=guardian_token,
        token_expires_at=datetime.fromtimestamp(token_expires_at, tz=UTC),
        session_expires_at=session.started_at
        + timedelta(minutes=settings.session_duration_minutes),
    )


def get_active_session(
    db: Session, session_id: str, settings: Settings | None = None
) -> tuple[ReadingSession, ChildProfile]:
    session = db.get(ReadingSession, session_id)
    if session is None:
        raise NotFoundError("找不到指定的學習階段。")
    if session.status != "ACTIVE":
        raise ForbiddenError("這個學習階段已經結束。")
    settings = settings or get_settings()
    expires_at = session.started_at + timedelta(minutes=settings.session_duration_minutes)
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    if now >= expires_at:
        from app.models import utc_now

        session.status = "ENDED"
        session.ended_at = utc_now()
        db.commit()
        raise ForbiddenError("這個學習階段已達時間上限，請和家長一起結束。")
    child = db.get(ChildProfile, session.child_id)
    if child is None:
        raise NotFoundError("找不到學習階段所屬的孩童設定。")
    return session, child


def end_session(db: Session, session_id: str, settings: Settings) -> SessionRead:
    from app.models import utc_now

    session, child = get_active_session(db, session_id)
    session.status = "ENDED"
    session.ended_at = utc_now()
    db.commit()
    return SessionRead(
        id=session.id,
        child_id=child.id,
        display_name=child.display_name,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        current_level=child.current_level,
        session_expires_at=session.started_at
        + timedelta(minutes=settings.session_duration_minutes),
    )
