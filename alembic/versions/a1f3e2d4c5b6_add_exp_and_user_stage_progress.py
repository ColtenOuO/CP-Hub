"""add exp to user_stats and create user_stage_progress table

Revision ID: a1f3e2d4c5b6
Revises: ce038a109e28
Create Date: 2026-06-16 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1f3e2d4c5b6"
down_revision: Union[str, Sequence[str], None] = "ce038a109e28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_stats", sa.Column("exp", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "user_stage_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Integer(), nullable=False),
        sa.Column("current_problem_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "stage_id", name="uq_user_stage"),
    )


def downgrade() -> None:
    op.drop_table("user_stage_progress")
    op.drop_column("user_stats", "exp")