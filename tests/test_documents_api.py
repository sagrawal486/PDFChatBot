import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.api.documents import router, upload_document
from app.services.document_service import DocumentService
from app.services.storage import LocalStorage, get_storage
from tests.fakes import FakeRepository, FakeStorage


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[UploadFile, int]] = []

    async def upload(self, file: UploadFile, user_id: int):
        self.calls.append((file, user_id))
        return {"id": 1, "file_name": file.filename, "status": "uploaded"}


def test_get_storage_returns_local_storage(monkeypatch) -> None:
    """Verify the API can use LocalStorage when the local backend is selected."""
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "local")

    storage = get_storage()

    assert isinstance(storage, LocalStorage)


def test_document_service_dependency_receives_storage_dependency() -> None:
    route = next(route for route in router.routes if route.endpoint is upload_document)
    service_dependency = next(
        dependency
        for dependency in route.dependant.dependencies
        if dependency.call.__name__ == "get_document_service"
    )
    storage_dependency = next(
        dependency
        for dependency in service_dependency.dependencies
        if dependency.call is get_storage
    )

    assert storage_dependency.call is get_storage


def test_post_documents_handler_forwards_file_and_authenticated_user() -> None:
    service = FakeService()
    upload = UploadFile(filename="report.pdf", file=BytesIO(b"%PDF-test"))
    user = type("User", (), {"id": 42})()

    result = asyncio.run(upload_document(upload, user, service))

    assert result == {"id": 1, "file_name": "report.pdf", "status": "uploaded"}
    assert service.calls == [(upload, 42)]


def test_post_documents_handler_preserves_invalid_content_response() -> None:
    service = DocumentService(FakeRepository(), FakeStorage())
    upload = UploadFile(
        filename="report.txt",
        file=BytesIO(b"not a pdf"),
        headers={"content-type": "text/plain"},
    )
    user = type("User", (), {"id": 42})()

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload_document(upload, user, service))

    assert error.value.status_code == 400
    assert error.value.detail == "Only PDF files are allowed"
