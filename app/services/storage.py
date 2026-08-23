from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import UploadFile


class Storage(Protocol):
    async def put(self, file: UploadFile) -> str:
        ...

    async def delete(self, storage_key: str) -> None:
        ...


def get_storage() -> Storage:
    return LocalStorage()


class LocalStorage:
    def __init__(self, upload_dir: Path = Path("uploads")) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def put(self, file: UploadFile) -> str:
        storage_key = f"{uuid4().hex}.pdf"
        file_path = self.upload_dir / storage_key

        with file_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)

        return storage_key

    async def delete(self, storage_key: str) -> None:
        file_path = (self.upload_dir / storage_key).resolve()
        upload_dir = self.upload_dir.resolve()

        if upload_dir not in file_path.parents:
            return

        if file_path.is_file():
            file_path.unlink()