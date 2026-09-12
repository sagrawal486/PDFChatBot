"""Document processing orchestration and status transitions."""

from typing import Protocol

from app.models.document import Document
from app.services.pdf_processing import DocumentProcessor
from app.services.storage import Storage
from app.services.embeddings import EmbeddingProvider


class DocumentRepositoryPort(Protocol):
    """Persistence operations required by the processing service."""

    def get_by_id(self, object_id: int) -> Document | None:
        """Return a document by ID or None."""

    def mark_status(self, document: Document, status: str) -> Document:
        """Persist a document status."""

    def replace_chunks(self, document_id: int, chunks: list[str]) -> list[object]:
        """Persist extracted chunks for a document."""

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[str, list[float]]],
    ) -> list[object]:
        """Persist extracted chunks with their embedding vectors."""


class DocumentProcessingService:
    """Load, process, and persist one document with explicit status changes."""

    def __init__(
        self,
        repository: DocumentRepositoryPort,
        storage: Storage,
        processor: DocumentProcessor,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Inject persistence, storage, and processing collaborators."""
        self.repository = repository
        self.storage = storage
        self.processor = processor
        self.embedding_provider = embedding_provider

    async def process(self, document_id: int) -> Document:
        """Process a document and mark it ready or failed."""
        document = self.repository.get_by_id(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} was not found")

        self.repository.mark_status(document, "processing")

        try:
            file_bytes = await self.storage.get(document.storage_key)
            chunks = self.processor.process(file_bytes)
            if self.embedding_provider is None:
                self.repository.replace_chunks(document.id, chunks)
            else:
                embedded_chunks = [
                    (chunk, self.embedding_provider.embed(chunk))
                    for chunk in chunks
                ]
                self.repository.replace_chunks_with_embeddings(
                    document.id,
                    embedded_chunks,
                )
            return self.repository.mark_status(document, "ready")
        except Exception:
            self.repository.mark_status(document, "failed")
            raise