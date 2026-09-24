"""Convert chunk embeddings to pgvector and add a similarity index.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3

Requires the pgvector extension (use the pgvector/pgvector Postgres image).
Embedding dimension is fixed at 1024 (Titan Text Embeddings v2 default).
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIMENSION = 1024


def upgrade() -> None:
    """Enable pgvector, convert the column and add an HNSW cosine index."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"ALTER TABLE document_chunks ALTER COLUMN embedding "
        f"TYPE vector({DIMENSION}) USING embedding::vector({DIMENSION})"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Revert to JSON-compatible text storage."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE text "
        "USING embedding::text"
    )
