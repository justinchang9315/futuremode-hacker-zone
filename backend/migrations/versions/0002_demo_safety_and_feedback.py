"""Add idempotency, inventory, feedback, and model audit data.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reading_attempts") as batch:
        batch.add_column(sa.Column("request_id", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("input_mode", sa.String(24), nullable=False, server_default="BROWSER_ASR")
        )
        batch.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))
        batch.create_index("ix_reading_attempts_request_id", ["request_id"], unique=True)

    with op.batch_alter_table("reading_assessments") as batch:
        batch.add_column(
            sa.Column("response_payload", sa.JSON(), nullable=False, server_default="{}")
        )

    with op.batch_alter_table("dialogue_turns") as batch:
        batch.add_column(sa.Column("request_id", sa.String(64), nullable=True))
        batch.create_index("ix_dialogue_turns_request_id", ["request_id"], unique=True)

    op.create_table(
        "reward_item_ownerships",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("item_code", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("equipped", sa.Boolean(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "item_code"),
    )
    op.create_index(
        "ix_reward_item_ownerships_child_id", "reward_item_ownerships", ["child_id"]
    )

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("assessment_id", sa.String(36), nullable=True),
        sa.Column("dialogue_turn_id", sa.String(36), nullable=True),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["reading_assessments.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["dialogue_turn_id"], ["dialogue_turns.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["reading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_events_session_id", "feedback_events", ["session_id"])
    op.create_index("ix_feedback_events_child_id", "feedback_events", ["child_id"])
    op.create_index("ix_feedback_events_assessment_id", "feedback_events", ["assessment_id"])
    op.create_index(
        "ix_feedback_events_dialogue_turn_id", "feedback_events", ["dialogue_turn_id"]
    )

    op.create_table(
        "model_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("child_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("output_valid", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["reading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_runs_session_id", "model_runs", ["session_id"])
    op.create_index("ix_model_runs_child_id", "model_runs", ["child_id"])


def downgrade() -> None:
    op.drop_index("ix_model_runs_child_id", table_name="model_runs")
    op.drop_index("ix_model_runs_session_id", table_name="model_runs")
    op.drop_table("model_runs")
    op.drop_index("ix_feedback_events_dialogue_turn_id", table_name="feedback_events")
    op.drop_index("ix_feedback_events_assessment_id", table_name="feedback_events")
    op.drop_index("ix_feedback_events_child_id", table_name="feedback_events")
    op.drop_index("ix_feedback_events_session_id", table_name="feedback_events")
    op.drop_table("feedback_events")
    op.drop_index("ix_reward_item_ownerships_child_id", table_name="reward_item_ownerships")
    op.drop_table("reward_item_ownerships")

    with op.batch_alter_table("dialogue_turns") as batch:
        batch.drop_index("ix_dialogue_turns_request_id")
        batch.drop_column("request_id")
    with op.batch_alter_table("reading_assessments") as batch:
        batch.drop_column("response_payload")
    with op.batch_alter_table("reading_attempts") as batch:
        batch.drop_index("ix_reading_attempts_request_id")
        batch.drop_column("duration_ms")
        batch.drop_column("input_mode")
        batch.drop_column("request_id")
