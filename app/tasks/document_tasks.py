"""Celery tasks for asynchronous document processing."""

import asyncio
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_service import DocumentProcessingService
from app.services.pdf_processing import (
    PdfDocumentProcessor,
    PdfTextExtractor,
    TextChunker,
)
from app.services.storage import get_storage
from app.worker import celery_app


def build_document_processing_service() -> tuple[DocumentProcessingService, Session]:
    """Build the real worker dependencies and return the DB session for cleanup."""
    db = SessionLocal()
    service = DocumentProcessingService(
        repository=DocumentRepository(db),
        storage=get_storage(),
        processor=PdfDocumentProcessor(
            extractor=PdfTextExtractor(),
            chunker=TextChunker(),
        ),
    )
    return service, db


def run_document_processing(
    document_id: int,
    service_factory: Callable[
        [], tuple[DocumentProcessingService, Session]
    ] = build_document_processing_service,
) -> None:
    """Run processing with a disposable service and database session."""
    service, db = service_factory()
    try:
        asyncio.run(service.process(document_id))
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.document_tasks.process_document",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=3,
)
def process_document(document_id: int) -> None:
    """Process one document in a Celery worker process."""
    run_document_processing(document_id)