"""Tests for document processing status transitions and persistence."""

import asyncio

import pytest

from app.models.document import Document
from app.services.document_processing_service import DocumentProcessingService


class FakeStorage:
    """Fake storage returning controlled document bytes."""

    def __init__(self, content: bytes = b"pdf") -> None:
        self.content = content

    async def get(self, storage_key: str) -> bytes:
        """Return bytes for the requested storage key."""
        return self.content


class FakeProcessor:
    """Fake processor returning controlled chunks."""

    def __init__(self, chunks: list[str] | None = None) -> None:
        self.chunks = chunks or ["first", "second"]

    def process(self, file_bytes: bytes) -> list[str]:
        """Return configured chunks."""
        return self.chunks


class FailingProcessor(FakeProcessor):
    """Processor that raises to test failed status handling."""

    def process(self, file_bytes: bytes) -> list[str]:
        """Raise a controlled processing error."""
        raise RuntimeError("processing failed")


class FakeEmbeddingProvider:
    """Fake embedding provider recording chunk text."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        """Return a deterministic vector for one chunk."""
        self.texts.append(text)
        return [float(len(text)), 1.0]


class FakeRepository:
    """Repository fake recording status and chunk operations."""

    def __init__(self) -> None:
        self.document = Document(id=7, storage_key="document.pdf", status="uploaded")
        self.statuses: list[str] = []
        self.saved_chunks: list[str] = []
        self.saved_embeddings: list[tuple[str, list[float]]] = []

    def get_by_id(self, object_id: int) -> Document | None:
        """Return the configured document."""
        return self.document if object_id == self.document.id else None

    def mark_status(self, document: Document, status: str) -> Document:
        """Record and apply a status update."""
        document.status = status
        self.statuses.append(status)
        return document

    def replace_chunks(self, document_id: int, chunks: list[str]) -> list[object]:
        """Record persisted chunks."""
        self.saved_chunks = chunks
        return []

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[str, list[float]]],
    ) -> list[object]:
        """Record chunks and their generated vectors."""
        self.saved_embeddings = chunks
        return []


def test_document_processing_marks_ready_and_persists_chunks() -> None:
    """Verify successful processing status transitions and chunk persistence."""
    repository = FakeRepository()
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FakeProcessor(),
    )

    document = asyncio.run(service.process(7))

    assert document.status == "ready"
    assert repository.statuses == ["processing", "ready"]
    assert repository.saved_chunks == ["first", "second"]


def test_document_processing_marks_failed_when_processing_raises() -> None:
    """Verify failed processing is persisted before the error is re-raised."""
    repository = FakeRepository()
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FailingProcessor(),
    )

    with pytest.raises(RuntimeError, match="processing failed"):
        asyncio.run(service.process(7))

    assert repository.statuses == ["processing", "failed"]


def test_document_processing_generates_and_persists_embeddings() -> None:
    """Verify each extracted chunk is embedded before persistence."""
    repository = FakeRepository()
    embedding_provider = FakeEmbeddingProvider()
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FakeProcessor(chunks=["first", "second"]),
        embedding_provider=embedding_provider,
    )

    document = asyncio.run(service.process(7))

    assert document.status == "ready"
    assert embedding_provider.texts == ["first", "second"]
    assert repository.saved_embeddings == [
        ("first", [5.0, 1.0]),
        ("second", [6.0, 1.0]),
    ]