"""PDF text extraction and bounded, page-aware text chunking services."""

from io import BytesIO
from typing import Any, Callable, NamedTuple, Protocol

from app.services.storage import Storage


class PageChunk(NamedTuple):
    """A bounded piece of text together with the 1-indexed page it came from."""

    page_number: int
    content: str


class TextExtractor(Protocol):
    """Extract normalized per-page text from PDF bytes."""

    def extract(self, file_bytes: bytes) -> list[str]:
        """Return one normalized text string per page, in page order."""


class PdfTextExtractor:
    """Extract per-page text from PDF bytes using pypdf."""

    def __init__(self, reader_factory: Callable[[Any], Any] | None = None) -> None:
        """Create an extractor with an optional reader factory for tests."""
        self.reader_factory = reader_factory or self._default_reader_factory

    def extract(self, file_bytes: bytes) -> list[str]:
        """Extract and normalize text for every page in a PDF."""
        reader = self.reader_factory(BytesIO(file_bytes))
        return [_normalize_text(page.extract_text() or "") for page in reader.pages]

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

    def split_pages(self, pages: list[str]) -> list[PageChunk]:
        """Chunk each page independently so every chunk keeps its source page."""
        return [
            PageChunk(page_number=page_number, content=chunk)
            for page_number, page_text in enumerate(pages, start=1)
            for chunk in self.split(page_text)
        ]


class DocumentProcessor(Protocol):
    """Process document bytes into searchable, page-aware text chunks."""

    def process(self, file_bytes: bytes) -> list[PageChunk]:
        """Extract text and return bounded chunks with their page numbers."""


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

    def process(self, file_bytes: bytes) -> list[PageChunk]:
        """Extract text from a PDF and split it into page-aware bounded chunks."""
        pages = self.extractor.extract(file_bytes)
        return self.chunker.split_pages(pages)


class StoredDocumentProcessor:
    """Load a stored document and process it into searchable chunks."""

    def __init__(self, storage: Storage, processor: DocumentProcessor) -> None:
        """Inject storage and PDF processing collaborators."""
        self.storage = storage
        self.processor = processor

    async def process(self, storage_key: str) -> list[PageChunk]:
        """Read a stored document and return its processed, page-aware chunks."""
        file_bytes = await self.storage.get(storage_key)
        return self.processor.process(file_bytes)


def _normalize_text(text: str) -> str:
    """Collapse whitespace so chunks contain consistent searchable text."""
    return " ".join(text.split())
