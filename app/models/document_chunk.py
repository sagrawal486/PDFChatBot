"""Database model for searchable document text chunks."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.settings import settings
from app.models.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - optional dependency in local/test environments
    Vector = None


USES_PGVECTOR = Vector is not None and settings.PGVECTOR_ENABLED

embedding_type = Vector(settings.PGVECTOR_DIMENSION) if USES_PGVECTOR else Text


class DocumentChunk(Base):
    """A bounded piece of extracted text belonging to one document."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | str | None] = mapped_column(embedding_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )