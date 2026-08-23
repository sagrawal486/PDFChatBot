from typing import Any

from fastapi import UploadFile


class FakeStorage:
    def __init__(self, storage_key: str = "stored-key.pdf") -> None:
        self.storage_key = storage_key
        self.uploads: list[UploadFile] = []
        self.upload_positions: list[int] = []

    async def put(self, file: UploadFile) -> str:
        self.uploads.append(file)
        self.upload_positions.append(file.file.tell())
        return self.storage_key

    async def delete(self, storage_key: str) -> None:
        return None


class FailingStorage(FakeStorage):
    async def put(self, file: UploadFile) -> str:
        raise RuntimeError("storage unavailable")


class FakeRepository:
    def __init__(self) -> None:
        self.created: list[Any] = []

    def create(self, document: Any) -> Any:
        self.created.append(document)
        return document