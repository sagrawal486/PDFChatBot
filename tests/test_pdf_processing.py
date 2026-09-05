"""Tests for PDF extraction, normalization, and text chunking."""

import asyncio

import pytest

from app.services.pdf_processing import (
    PdfDocumentProcessor,
    PdfTextExtractor,
    StoredDocumentProcessor,
    TextChunker,
)


class FakePage:
    """Fake PDF page returning controlled text for extractor tests."""

    def __init__(self, text: str | None) -> None:
        self.text = text

    def extract_text(self) -> str | None:
        """Return the configured page text."""
        return self.text


class FakeReader:
    """Fake PDF reader exposing the pypdf pages interface."""

    def __init__(self, stream) -> None:
        self.stream = stream
        self.pages = [FakePage(" First page.\n\n"), FakePage(None), FakePage("Second page.")]


class FakeExtractor:
    """Fake extractor for testing processor composition."""

    def extract(self, file_bytes: bytes) -> str:
        """Return deterministic text without parsing a real PDF."""
        return "alpha beta gamma delta"


class FakeStorage:
    """Fake storage that records the requested storage key."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.requested_keys: list[str] = []

    async def get(self, storage_key: str) -> bytes:
        """Return configured bytes for the requested object key."""
        self.requested_keys.append(storage_key)
        return self.content


def test_pdf_text_extractor_normalizes_text() -> None:
    """Verify that page text is combined and whitespace is normalized."""
    extractor = PdfTextExtractor(reader_factory=FakeReader)

    text = extractor.extract(b"fake-pdf")

    assert text == "First page. Second page."


def test_text_chunker_returns_bounded_overlapping_chunks() -> None:
    """Verify chunk size and overlap behavior for searchable text."""
    chunker = TextChunker(chunk_size=10, overlap=2)

    chunks = chunker.split("abcdefghij klmnopqrst")

    assert chunks == ["abcdefghij", "ij klmnopq", "pqrst"]
    assert all(len(chunk) <= 10 for chunk in chunks)


def test_text_chunker_returns_empty_list_for_blank_text() -> None:
    """Verify blank documents do not create empty searchable chunks."""
    assert TextChunker().split(" \n\t") == []


def test_text_chunker_rejects_invalid_configuration() -> None:
    """Verify invalid chunk boundaries fail with clear errors."""
    with pytest.raises(ValueError, match="chunk_size"):
        TextChunker(chunk_size=0)

    with pytest.raises(ValueError, match="overlap"):
        TextChunker(chunk_size=10, overlap=10)


def test_pdf_document_processor_composes_extractor_and_chunker() -> None:
    """Verify the processor coordinates injected extraction and chunking."""
    processor = PdfDocumentProcessor(
        extractor=FakeExtractor(),
        chunker=TextChunker(chunk_size=10, overlap=0),
    )

    chunks = processor.process(b"fake-pdf")

    assert chunks == ["alpha beta", " gamma del", "ta"]


def test_stored_document_processor_loads_then_processes_document() -> None:
    """Verify stored bytes flow through storage and the processor."""
    storage = FakeStorage(content=b"stored-pdf")
    processor = StoredDocumentProcessor(
        storage=storage,
        processor=PdfDocumentProcessor(
            extractor=FakeExtractor(),
            chunker=TextChunker(chunk_size=10, overlap=0),
        ),
    )

    chunks = asyncio.run(processor.process("document-key"))

    assert storage.requested_keys == ["document-key"]
    assert chunks == ["alpha beta", " gamma del", "ta"]