"""cabin air readings per user-night (ppCO2, temperature, humidity)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cabin_readings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ppco2_mmhg", sa.Float(), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("rh_pct", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cabin_readings")),
        sa.UniqueConstraint("user_id", "date", name=op.f("uq_cabin_readings_user_id_date")),
    )
    op.create_index(
        op.f("ix_cabin_readings_user_id"), "cabin_readings", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cabin_readings_user_id"), table_name="cabin_readings")
    op.drop_table("cabin_readings")
