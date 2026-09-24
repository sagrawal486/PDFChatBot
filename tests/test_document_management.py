"""Tests for listing, fetching and deleting documents with ownership checks."""

import asyncio

import pytest
from fastapi import HTTPException

from app.services.document_service import DocumentService
from tests.fakes import FakeStorage


class Doc:
    def __init__(self, id: int, user_id: int, storage_key: str = "k.pdf") -> None:
        self.id = id
        self.user_id = user_id
        self.storage_key = storage_key


class OwnedRepository:
    def __init__(self, docs: list[Doc]) -> None:
        self.docs = docs
        self.deleted: list[Doc] = []

    def list_for_user(self, user_id: int) -> list[Doc]:
        return [d for d in self.docs if d.user_id == user_id]

    def get_for_user(self, document_id: int, user_id: int):
        return next((d for d in self.docs if d.id == document_id and d.user_id == user_id), None)

    def delete(self, document: Doc) -> None:
        self.deleted.append(document)


class RecordingStorage(FakeStorage):
    def __init__(self) -> None:
        super().__init__()
        self.deleted_keys: list[str] = []

    async def delete(self, storage_key: str) -> None:
        self.deleted_keys.append(storage_key)


def make_service() -> tuple[DocumentService, OwnedRepository, RecordingStorage]:
    repository = OwnedRepository([Doc(1, user_id=7), Doc(2, user_id=8)])
    storage = RecordingStorage()
    return DocumentService(repository, storage), repository, storage


def test_list_documents_returns_only_the_users_documents() -> None:
    service, _, _ = make_service()

    assert [d.id for d in service.list_documents(7)] == [1]


def test_get_document_hides_other_users_documents() -> None:
    service, _, _ = make_service()

    with pytest.raises(HTTPException) as error:
        service.get_document(2, user_id=7)

    assert error.value.status_code == 404


def test_delete_document_removes_file_and_row() -> None:
    service, repository, storage = make_service()

    asyncio.run(service.delete_document(1, user_id=7))

    assert storage.deleted_keys == ["k.pdf"]
    assert [d.id for d in repository.deleted] == [1]


def test_delete_document_rejects_other_users_documents() -> None:
    service, repository, storage = make_service()

    with pytest.raises(HTTPException) as error:
        asyncio.run(service.delete_document(2, user_id=7))

    assert error.value.status_code == 404
    assert storage.deleted_keys == []
    assert repository.deleted == []
