"""Initial child companion schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "child_profiles",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("age_profile", sa.String(16), nullable=False),
        sa.Column("current_level", sa.Integer(), nullable=False),
        sa.Column("guardian_approved_level3", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("reference_text", sa.Text(), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("license_label", sa.String(128), nullable=False),
        sa.Column("scoring_config", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "guardian_consents",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("consent_version", sa.String(32), nullable=False),
        sa.Column("guardian_present", sa.Boolean(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guardian_consents_child_id", "guardian_consents", ["child_id"])
    op.create_table(
        "reading_sessions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("guardian_consent_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["guardian_consent_id"], ["guardian_consents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reading_sessions_child_id", "reading_sessions", ["child_id"])
    op.create_table(
        "reading_attempts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("content_id", sa.String(64), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("asr_quality", sa.String(16), nullable=False),
        sa.Column("provider_confidence", sa.Float(), nullable=True),
        sa.Column("audio_quality_score", sa.Float(), nullable=False),
        sa.Column("long_pause_count", sa.Integer(), nullable=False),
        sa.Column("restart_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["reading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reading_attempts_child_id", "reading_attempts", ["child_id"])
    op.create_index("ix_reading_attempts_content_id", "reading_attempts", ["content_id"])
    op.create_index("ix_reading_attempts_session_id", "reading_attempts", ["session_id"])
    op.create_table(
        "reading_assessments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("assessment_confidence", sa.Float(), nullable=False),
        sa.Column("score_policy_version", sa.String(32), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["reading_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reading_assessments_attempt_id",
        "reading_assessments",
        ["attempt_id"],
        unique=True,
    )
    op.create_table(
        "personal_bests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("content_id", sa.String(64), nullable=False),
        sa.Column("best_score", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["reading_assessments.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "content_id"),
    )
    op.create_index("ix_personal_bests_child_id", "personal_bests", ["child_id"])
    op.create_index("ix_personal_bests_content_id", "personal_bests", ["content_id"])
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("coin_balance", sa.Integer(), nullable=False),
        sa.Column("gem_balance", sa.Integer(), nullable=False),
        sa.Column("lifetime_coins", sa.Integer(), nullable=False),
        sa.Column("lifetime_gems", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallets_child_id", "wallets", ["child_id"], unique=True)
    op.create_table(
        "reward_transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("assessment_id", sa.String(36), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["reading_assessments.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reward_transactions_child_id", "reward_transactions", ["child_id"]
    )
    op.create_index(
        "ix_reward_transactions_idempotency_key",
        "reward_transactions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_table(
        "capability_unlocks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("guardian_approved", sa.Boolean(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "level"),
    )
    op.create_index("ix_capability_unlocks_child_id", "capability_unlocks", ["child_id"])
    op.create_table(
        "dialogue_turns",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("safety_level", sa.Integer(), nullable=False),
        sa.Column("companion_level", sa.Integer(), nullable=False),
        sa.Column("speech", sa.Text(), nullable=True),
        sa.Column("body_actions", sa.JSON(), nullable=False),
        sa.Column("response_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["reading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dialogue_turns_child_id", "dialogue_turns", ["child_id"])
    op.create_index("ix_dialogue_turns_session_id", "dialogue_turns", ["session_id"])
    op.create_table(
        "safety_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("safety_level", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("response_script_id", sa.String(64), nullable=False),
        sa.Column("minimal_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["reading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_events_child_id", "safety_events", ["child_id"])
    op.create_index("ix_safety_events_session_id", "safety_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_safety_events_session_id", table_name="safety_events")
    op.drop_index("ix_safety_events_child_id", table_name="safety_events")
    op.drop_table("safety_events")
    op.drop_index("ix_dialogue_turns_session_id", table_name="dialogue_turns")
    op.drop_index("ix_dialogue_turns_child_id", table_name="dialogue_turns")
    op.drop_table("dialogue_turns")
    op.drop_index("ix_capability_unlocks_child_id", table_name="capability_unlocks")
    op.drop_table("capability_unlocks")
    op.drop_index(
        "ix_reward_transactions_idempotency_key", table_name="reward_transactions"
    )
    op.drop_index("ix_reward_transactions_child_id", table_name="reward_transactions")
    op.drop_table("reward_transactions")
    op.drop_index("ix_wallets_child_id", table_name="wallets")
    op.drop_table("wallets")
    op.drop_index("ix_personal_bests_content_id", table_name="personal_bests")
    op.drop_index("ix_personal_bests_child_id", table_name="personal_bests")
    op.drop_table("personal_bests")
    op.drop_index("ix_reading_assessments_attempt_id", table_name="reading_assessments")
    op.drop_table("reading_assessments")
    op.drop_index("ix_reading_attempts_session_id", table_name="reading_attempts")
    op.drop_index("ix_reading_attempts_content_id", table_name="reading_attempts")
    op.drop_index("ix_reading_attempts_child_id", table_name="reading_attempts")
    op.drop_table("reading_attempts")
    op.drop_index("ix_reading_sessions_child_id", table_name="reading_sessions")
    op.drop_table("reading_sessions")
    op.drop_index("ix_guardian_consents_child_id", table_name="guardian_consents")
    op.drop_table("guardian_consents")
    op.drop_table("content_items")
    op.drop_table("child_profiles")
