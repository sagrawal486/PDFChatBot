"""Document-processing dispatch boundary."""

from typing import Protocol

from app.tasks.document_tasks import process_document


class DocumentDispatcher(Protocol):
    """Queue document processing without coupling services to Celery."""

    def enqueue(self, document_id: int) -> None:
        """Queue processing for a persisted document."""


class CeleryDocumentDispatcher:
    """Dispatch document processing to the Celery broker."""

    def enqueue(self, document_id: int) -> None:
        """Send a document ID to the processing task."""
        process_document.delay(document_id)