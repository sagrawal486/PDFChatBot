from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import UploadFile

from app.core.settings import settings
from app.services.s3_storage import S3Storage


class Storage(Protocol):
    async def put(self, file: UploadFile) -> str:
        ...

    async def get(self, storage_key: str) -> bytes:
        ...

    async def delete(self, storage_key: str) -> None:
        ...


def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "local":
        return LocalStorage()

    if settings.STORAGE_BACKEND == "s3":
        if not settings.S3_BUCKET:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND is s3")

        return S3Storage(
            bucket=settings.S3_BUCKET,
            region=settings.AWS_REGION,
        )

    raise ValueError(
        "Unsupported STORAGE_BACKEND. Expected 'local' or 's3'."
    )


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

    async def get(self, storage_key: str) -> bytes:
        """Read a stored object after validating it stays in the upload directory."""
        file_path = (self.upload_dir / storage_key).resolve()
        upload_dir = self.upload_dir.resolve()

        if upload_dir not in file_path.parents or not file_path.is_file():
            raise FileNotFoundError(storage_key)

        return file_path.read_bytes()