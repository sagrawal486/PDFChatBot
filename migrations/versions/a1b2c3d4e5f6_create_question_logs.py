"""Create question_logs for per-user daily usage limiting.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the question_logs table used to count a user's usage over time."""
    op.create_table(
        "question_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_question_logs_user_id"),
        "question_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the question_logs table."""
    op.drop_index(op.f("ix_question_logs_user_id"), table_name="question_logs")
    op.drop_table("question_logs")
