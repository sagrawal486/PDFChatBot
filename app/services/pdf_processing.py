"""PDF text extraction and bounded text chunking services."""

from io import BytesIO
from typing import Any, Callable, Protocol

from app.services.storage import Storage


class TextExtractor(Protocol):
    """Extract normalized text from PDF bytes."""

    def extract(self, file_bytes: bytes) -> str:
        """Return text extracted from a PDF document."""


class PdfTextExtractor:
    """Extract text from PDF bytes using pypdf."""

    def __init__(self, reader_factory: Callable[[Any], Any] | None = None) -> None:
        """Create an extractor with an optional reader factory for tests."""
        self.reader_factory = reader_factory or self._default_reader_factory

    def extract(self, file_bytes: bytes) -> str:
        """Extract and normalize text from every page in a PDF."""
        reader = self.reader_factory(BytesIO(file_bytes))
        page_text = [page.extract_text() or "" for page in reader.pages]
        return _normalize_text("\n".join(page_text))

    @staticmethod
    def _default_reader_factory(stream: BytesIO) -> Any:
        """Create the pypdf reader lazily so fakes do not need the dependency."""
        from pypdf import PdfReader

        return PdfReader(stream)


class TextChunker:
    """Split text into bounded, overlapping character chunks."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100) -> None:
        """Configure chunk size and overlap with basic validation."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be between zero and chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        """Return bounded chunks while preserving a small overlap for retrieval."""
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return []

        step = self.chunk_size - self.overlap
        return [
            normalized_text[start : start + self.chunk_size]
            for start in range(0, len(normalized_text), step)
        ]


class DocumentProcessor(Protocol):
    """Process document bytes into searchable text chunks."""

    def process(self, file_bytes: bytes) -> list[str]:
        """Extract text and return bounded chunks."""


class PdfDocumentProcessor:
    """Compose PDF extraction and text chunking behind one service."""

    def __init__(
        self,
        extractor: TextExtractor,
        chunker: TextChunker,
    ) -> None:
        """Inject processing collaborators so the service remains testable."""
        self.extractor = extractor
        self.chunker = chunker

    def process(self, file_bytes: bytes) -> list[str]:
        """Extract text from a PDF and split it into bounded chunks."""
        text = self.extractor.extract(file_bytes)
        return self.chunker.split(text)


class StoredDocumentProcessor:
    """Load a stored document and process it into searchable chunks."""

    def __init__(self, storage: Storage, processor: DocumentProcessor) -> None:
        """Inject storage and PDF processing collaborators."""
        self.storage = storage
        self.processor = processor

    async def process(self, storage_key: str) -> list[str]:
        """Read a stored document and return its processed text chunks."""
        file_bytes = await self.storage.get(storage_key)
        return self.processor.process(file_bytes)


def _normalize_text(text: str) -> str:
    """Collapse whitespace so chunks contain consistent searchable text."""
    return " ".join(text.split())