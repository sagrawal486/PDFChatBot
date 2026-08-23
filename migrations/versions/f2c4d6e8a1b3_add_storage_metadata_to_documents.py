"""Add storage metadata to documents

Revision ID: f2c4d6e8a1b3
Revises: edea7da9f42b
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2c4d6e8a1b3"
down_revision: Union[str, Sequence[str], None] = "edea7da9f42b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("storage_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("file_size", sa.Integer(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE documents SET storage_key = file_path "
            "WHERE storage_key IS NULL"
        )
    )
    op.alter_column(
        "documents",
        "storage_key",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("documents", "file_path")


def downgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("file_path", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE documents SET file_path = storage_key "
            "WHERE file_path IS NULL"
        )
    )
    op.alter_column(
        "documents",
        "file_path",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("documents", "file_size")
    op.drop_column("documents", "content_type")
    op.drop_column("documents", "storage_key")