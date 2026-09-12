"""Add embeddings to document chunks.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add an optional JSON-encoded embedding column."""
    op.add_column(
        "document_chunks",
        sa.Column("embedding", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove stored chunk embeddings."""
    op.drop_column("document_chunks", "embedding")