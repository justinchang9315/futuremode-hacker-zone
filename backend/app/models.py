from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # 孩子自己輸入的暱稱，只用來在同一台裝置上分辨是誰，可以留空。
    display_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    age: Mapped[int] = mapped_column(Integer)
    grade_level: Mapped[int] = mapped_column(Integer)
    age_profile: Mapped[str] = mapped_column(String(16), default="6-8")
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    guardian_approved_level3: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GuardianConsent(Base):
    __tablename__ = "guardian_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    consent_version: Mapped[str] = mapped_column(String(32))
    guardian_present: Mapped[bool] = mapped_column(Boolean)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), default="POEM")
    reference_text: Mapped[str] = mapped_column(Text)
    grade_level: Mapped[int] = mapped_column(Integer, default=2)
    source: Mapped[str] = mapped_column(String(256))
    license_label: Mapped[str] = mapped_column(String(128))
    scoring_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    guardian_consent_id: Mapped[str] = mapped_column(ForeignKey("guardian_consents.id"))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadingAttempt(Base):
    __tablename__ = "reading_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("reading_sessions.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    input_mode: Mapped[str] = mapped_column(String(24), default="BROWSER_ASR")
    transcript: Mapped[str] = mapped_column(Text)
    asr_quality: Mapped[str] = mapped_column(String(16))
    provider_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_quality_score: Mapped[float] = mapped_column(Float)
    long_pause_count: Mapped[int] = mapped_column(Integer, default=0)
    restart_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReadingAssessment(Base):
    __tablename__ = "reading_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("reading_attempts.id"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(24))
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_confidence: Mapped[float] = mapped_column(Float)
    score_policy_version: Mapped[str] = mapped_column(String(32))
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PersonalBest(Base):
    __tablename__ = "personal_bests"
    __table_args__ = (UniqueConstraint("child_id", "content_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), index=True)
    best_score: Mapped[int] = mapped_column(Integer)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("reading_assessments.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(
        ForeignKey("child_profiles.id"), unique=True, index=True
    )
    coin_balance: Mapped[int] = mapped_column(Integer, default=0)
    gem_balance: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_coins: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_gems: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RewardTransaction(Base):
    __tablename__ = "reward_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("reading_assessments.id"), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    policy_version: Mapped[str] = mapped_column(String(32))
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RewardItemOwnership(Base):
    __tablename__ = "reward_item_ownerships"
    __table_args__ = (UniqueConstraint("child_id", "item_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    item_code: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CapabilityUnlock(Base):
    __tablename__ = "capability_unlocks"
    __table_args__ = (UniqueConstraint("child_id", "level"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)
    guardian_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DialogueTurn(Base):
    __tablename__ = "dialogue_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("reading_sessions.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    input_text: Mapped[str] = mapped_column(Text)
    safety_level: Mapped[int] = mapped_column(Integer, default=0)
    companion_level: Mapped[int] = mapped_column(Integer)
    speech: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    response_source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("reading_sessions.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    safety_level: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(64))
    response_script_id: Mapped[str] = mapped_column(String(64))
    minimal_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("reading_sessions.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("reading_assessments.id"), nullable=True, index=True
    )
    dialogue_turn_id: Mapped[str | None] = mapped_column(
        ForeignKey("dialogue_turns.id"), nullable=True, index=True
    )
    helpful: Mapped[bool] = mapped_column(Boolean)
    relevance: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("reading_sessions.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    operation: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32))
    success: Mapped[bool] = mapped_column(Boolean)
    output_valid: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
