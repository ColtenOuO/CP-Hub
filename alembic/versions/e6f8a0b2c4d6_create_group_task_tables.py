"""create group_tasks and group_task_problems tables

Revision ID: e6f8a0b2c4d6
Revises: d4e6f8a0b2c4
Create Date: 2026-06-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e6f8a0b2c4d6"
down_revision: Union[str, Sequence[str], None] = "d4e6f8a0b2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reward_exp", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "group_task_problems",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_task_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("difficulty", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title_slug", sa.String(), nullable=False),
        sa.Column("claimed_by", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_task_id"], ["group_tasks.id"]),
        sa.ForeignKeyConstraint(["claimed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_task_id", "code"),
    )


def downgrade() -> None:
    op.drop_table("group_task_problems")
    op.drop_table("group_tasks")
