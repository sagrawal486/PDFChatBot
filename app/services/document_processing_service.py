"""Document processing orchestration and status transitions."""

import logging
from typing import Protocol

from app.models.document import Document
from app.services.pdf_processing import DocumentProcessor
from app.services.storage import Storage
from app.services.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


class DocumentRepositoryPort(Protocol):
    """Persistence operations required by the processing service."""

    def get_by_id(self, object_id: int) -> Document | None:
        """Return a document by ID or None."""

    def mark_status(self, document: Document, status: str) -> Document:
        """Persist a document status."""

    def replace_chunks(self, document_id: int, chunks: list[tuple[int, str]]) -> list[object]:
        """Persist extracted (page_number, content) chunks for a document."""

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[int, str, list[float]]],
    ) -> list[object]:
        """Persist extracted (page_number, content, embedding) chunks."""


class DocumentProcessingService:
    """Load, process, and persist one document with explicit status changes."""

    def __init__(
        self,
        repository: DocumentRepositoryPort,
        storage: Storage,
        processor: DocumentProcessor,
        embedding_provider: EmbeddingProvider | None = None,
        max_chunks: int | None = None,
    ) -> None:
        """Inject persistence, storage, and processing collaborators.

        max_chunks bounds embedding/storage cost for very large documents: chunks
        beyond that count are dropped rather than embedded.
        """
        self.repository = repository
        self.storage = storage
        self.processor = processor
        self.embedding_provider = embedding_provider
        self.max_chunks = max_chunks

    async def process(self, document_id: int) -> Document:
        """Process a document and mark it ready or failed."""
        document = self.repository.get_by_id(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} was not found")

        self.repository.mark_status(document, "processing")

        try:
            file_bytes = await self.storage.get(document.storage_key)
            chunks = self.processor.process(file_bytes)

            if self.max_chunks is not None and len(chunks) > self.max_chunks:
                logger.warning(
                    "document %s produced %d chunks, truncating to %d",
                    document.id,
                    len(chunks),
                    self.max_chunks,
                )
                chunks = chunks[: self.max_chunks]

            if self.embedding_provider is None:
                self.repository.replace_chunks(
                    document.id,
                    [(chunk.page_number, chunk.content) for chunk in chunks],
                )
            else:
                texts = [chunk.content for chunk in chunks]
                embed_batch = getattr(self.embedding_provider, "embed_batch", None)
                vectors = (
                    embed_batch(texts)
                    if embed_batch is not None
                    else [self.embedding_provider.embed(text) for text in texts]
                )
                embedded_chunks = [
                    (chunk.page_number, chunk.content, vector)
                    for chunk, vector in zip(chunks, vectors)
                ]
                self.repository.replace_chunks_with_embeddings(
                    document.id,
                    embedded_chunks,
                )
            return self.repository.mark_status(document, "ready")
        except Exception:
            self.repository.mark_status(document, "failed")
            raise