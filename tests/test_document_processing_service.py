"""Tests for document processing status transitions and persistence."""

import asyncio

import pytest

from app.models.document import Document
from app.services.document_processing_service import DocumentProcessingService
from app.services.pdf_processing import PageChunk


class FakeStorage:
    """Fake storage returning controlled document bytes."""

    def __init__(self, content: bytes = b"pdf") -> None:
        self.content = content

    async def get(self, storage_key: str) -> bytes:
        """Return bytes for the requested storage key."""
        return self.content


class FakeProcessor:
    """Fake processor returning controlled page-aware chunks."""

    def __init__(self, chunks: list[PageChunk] | None = None) -> None:
        self.chunks = chunks or [PageChunk(1, "first"), PageChunk(1, "second")]

    def process(self, file_bytes: bytes) -> list[PageChunk]:
        """Return configured chunks."""
        return self.chunks


class FailingProcessor(FakeProcessor):
    """Processor that raises to test failed status handling."""

    def process(self, file_bytes: bytes) -> list[PageChunk]:
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


class FakeBatchEmbeddingProvider:
    """Fake embedding provider that embeds many chunks in one batched call."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def embed(self, text: str) -> list[float]:
        """Return a deterministic vector for one chunk (unused when batching)."""
        return [float(len(text)), 1.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Record the batch and return deterministic vectors in the same order."""
        self.batches.append(texts)
        return [[float(len(text)), 1.0] for text in texts]


class FakeRepository:
    """Repository fake recording status and chunk operations."""

    def __init__(self) -> None:
        self.document = Document(id=7, storage_key="document.pdf", status="uploaded")
        self.statuses: list[str] = []
        self.saved_chunks: list[tuple[int, str]] = []
        self.saved_embeddings: list[tuple[int, str, list[float]]] = []

    def get_by_id(self, object_id: int) -> Document | None:
        """Return the configured document."""
        return self.document if object_id == self.document.id else None

    def mark_status(self, document: Document, status: str) -> Document:
        """Record and apply a status update."""
        document.status = status
        self.statuses.append(status)
        return document

    def replace_chunks(self, document_id: int, chunks: list[tuple[int, str]]) -> list[object]:
        """Record persisted chunks."""
        self.saved_chunks = chunks
        return []

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[int, str, list[float]]],
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
    assert repository.saved_chunks == [(1, "first"), (1, "second")]


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
        processor=FakeProcessor(chunks=[PageChunk(1, "first"), PageChunk(2, "second")]),
        embedding_provider=embedding_provider,
    )

    document = asyncio.run(service.process(7))

    assert document.status == "ready"
    assert embedding_provider.texts == ["first", "second"]
    assert repository.saved_embeddings == [
        (1, "first", [5.0, 1.0]),
        (2, "second", [6.0, 1.0]),
    ]


def test_document_processing_uses_embed_batch_when_the_provider_supports_it() -> None:
    """Verify batching providers are used instead of embedding one chunk at a time."""
    repository = FakeRepository()
    embedding_provider = FakeBatchEmbeddingProvider()
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FakeProcessor(chunks=[PageChunk(1, "first"), PageChunk(2, "second")]),
        embedding_provider=embedding_provider,
    )

    document = asyncio.run(service.process(7))

    assert document.status == "ready"
    assert embedding_provider.batches == [["first", "second"]]
    assert repository.saved_embeddings == [
        (1, "first", [5.0, 1.0]),
        (2, "second", [6.0, 1.0]),
    ]


def test_document_processing_truncates_chunks_beyond_the_configured_maximum() -> None:
    """Verify a very large document is capped rather than fully embedded."""
    repository = FakeRepository()
    embedding_provider = FakeEmbeddingProvider()
    chunks = [PageChunk(1, f"chunk-{i}") for i in range(5)]
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FakeProcessor(chunks=chunks),
        embedding_provider=embedding_provider,
        max_chunks=3,
    )

    document = asyncio.run(service.process(7))

    assert document.status == "ready"
    assert len(repository.saved_embeddings) == 3
    assert [content for _, content, _ in repository.saved_embeddings] == [
        "chunk-0",
        "chunk-1",
        "chunk-2",
    ]


def test_document_processing_truncates_chunks_without_an_embedding_provider() -> None:
    """Verify the chunk cap also applies when no embedding provider is configured."""
    repository = FakeRepository()
    chunks = [PageChunk(1, f"chunk-{i}") for i in range(5)]
    service = DocumentProcessingService(
        repository=repository,
        storage=FakeStorage(),
        processor=FakeProcessor(chunks=chunks),
        max_chunks=2,
    )

    asyncio.run(service.process(7))

    assert repository.saved_chunks == [(1, "chunk-0"), (1, "chunk-1")]