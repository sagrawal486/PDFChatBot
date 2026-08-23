import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.core.settings import settings
from app.services.document_service import DocumentService
from tests.fakes import FakeRepository, FakeStorage, FailingStorage


def make_upload(
    content: bytes = b"%PDF-test",
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        filename="report.pdf",
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


def test_upload_uses_storage_abstraction_and_persists_metadata() -> None:
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)

    document = asyncio.run(service.upload(make_upload(), user_id=7))

    assert storage.uploads
    assert repository.created == [document]
    assert document.user_id == 7
    assert document.file_name == "report.pdf"
    assert document.storage_key == "stored-key.pdf"
    assert document.content_type == "application/pdf"
    assert document.file_size == len(b"%PDF-test")
    assert document.status == "uploaded"


def test_upload_rejects_non_pdf_content_type() -> None:
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            service.upload(
                make_upload(content_type="text/plain"),
                user_id=7,
            )
        )

    assert error.value.status_code == 400
    assert repository.created == []
    assert storage.uploads == []


def test_upload_rejects_invalid_pdf_signature() -> None:
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.upload(make_upload(content=b"not a PDF"), user_id=7))

    assert error.value.status_code == 400
    assert error.value.detail == "PDF file is invalid"
    assert repository.created == []
    assert storage.uploads == []


def test_upload_rejects_file_larger_than_configured_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)
    large_content = b"%PDF-" + b"x" * (1024 * 1024)

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.upload(make_upload(content=large_content), user_id=7))

    assert error.value.status_code == 400
    assert error.value.detail == "File size exceeds the maximum allowed size"
    assert repository.created == []
    assert storage.uploads == []


def test_upload_accepts_file_exactly_at_configured_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)
    content = b"%PDF-" + b"x" * (1024 * 1024 - len(b"%PDF-"))

    document = asyncio.run(service.upload(make_upload(content=content), user_id=7))

    assert document.file_size == 1024 * 1024


def test_upload_resets_file_pointer_before_storage(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    repository = FakeRepository()
    storage = FakeStorage()
    service = DocumentService(repository, storage)
    upload = make_upload(content=b"%PDF-test")

    asyncio.run(service.upload(upload, user_id=7))

    assert storage.upload_positions == [0]


def test_upload_does_not_persist_when_storage_fails() -> None:
    repository = FakeRepository()
    service = DocumentService(repository, FailingStorage())

    with pytest.raises(RuntimeError, match="storage unavailable"):
        asyncio.run(service.upload(make_upload(), user_id=7))

    assert repository.created == []
