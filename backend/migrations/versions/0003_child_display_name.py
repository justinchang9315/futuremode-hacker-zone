"""Add an optional child nickname so one device can tell profiles apart.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("child_profiles") as batch:
        batch.add_column(sa.Column("display_name", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("child_profiles") as batch:
        batch.drop_column("display_name")
