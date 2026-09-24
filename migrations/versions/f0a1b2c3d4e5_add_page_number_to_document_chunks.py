"""Add page_number to document chunks for page-aware citations.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add an optional page number column; existing rows have no page recorded."""
    op.add_column(
        "document_chunks",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove the page number column."""
    op.drop_column("document_chunks", "page_number")
