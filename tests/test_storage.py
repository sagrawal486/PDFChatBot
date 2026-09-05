import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.services.s3_storage import S3Storage
from app.services.storage import LocalStorage, get_storage


def run_async(coroutine):
    return asyncio.run(coroutine)


def make_upload(filename: str = "original.pdf", content: bytes = b"pdf data") -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_put_stores_file_under_configured_directory(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    storage_key = run_async(storage.put(make_upload()))

    stored_path = tmp_path / storage_key
    assert stored_path.parent == tmp_path
    assert stored_path.is_file()


def test_put_generates_server_side_name(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    storage_key = run_async(storage.put(make_upload("../../unsafe.pdf")))

    assert Path(storage_key).name != "../../unsafe.pdf"
    assert Path(storage_key).name.endswith(".pdf")


def test_put_generates_unique_keys(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    first_key = run_async(storage.put(make_upload()))
    second_key = run_async(storage.put(make_upload()))

    assert first_key != second_key


def test_put_preserves_uploaded_bytes(tmp_path: Path) -> None:
    content = b"%PDF-1.7\nexample"
    storage = LocalStorage(tmp_path)

    storage_key = run_async(storage.put(make_upload(content=content)))

    assert (tmp_path / storage_key).read_bytes() == content


def test_delete_removes_stored_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage_key = run_async(storage.put(make_upload()))
    stored_path = tmp_path / storage_key

    run_async(storage.delete(stored_path.name))

    assert not stored_path.exists()


def test_delete_ignores_path_outside_upload_directory(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    outside_file = tmp_path.parent / "outside.pdf"
    outside_file.write_bytes(b"keep me")

    run_async(storage.delete(f"../{outside_file.name}"))

    assert outside_file.exists()
    outside_file.unlink()


def test_delete_ignores_missing_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    run_async(storage.delete("missing.pdf"))


def test_get_reads_stored_file(tmp_path: Path) -> None:
    """Verify that LocalStorage.get() returns the original bytes."""
    storage = LocalStorage(tmp_path)
    content = b"%PDF-local"
    storage_key = run_async(storage.put(make_upload(content=content)))

    assert run_async(storage.get(storage_key)) == content


def test_get_rejects_missing_or_outside_file(tmp_path: Path) -> None:
    """Verify that LocalStorage.get() cannot read missing or unsafe paths."""
    storage = LocalStorage(tmp_path)

    with pytest.raises(FileNotFoundError):
        run_async(storage.get("missing.pdf"))


def test_get_storage_returns_local_storage_by_default(monkeypatch) -> None:
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "local")

    storage = get_storage()

    assert isinstance(storage, LocalStorage)


def test_get_storage_returns_s3_storage_with_configured_bucket(monkeypatch) -> None:
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("app.services.storage.settings.S3_BUCKET", "learning-bucket")
    monkeypatch.setattr("app.services.storage.settings.AWS_REGION", "eu-west-1")
    injected_client = object()

    class TestS3Storage(S3Storage):
        def __init__(self, bucket: str, region: str) -> None:
            super().__init__(bucket=bucket, region=region, client=injected_client)

    monkeypatch.setattr("app.services.storage.S3Storage", TestS3Storage)

    storage = get_storage()

    assert isinstance(storage, TestS3Storage)
    assert storage.bucket == "learning-bucket"
    assert storage.client is injected_client


def test_get_storage_rejects_missing_s3_bucket(monkeypatch) -> None:
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("app.services.storage.settings.S3_BUCKET", "")

    with pytest.raises(ValueError, match="S3_BUCKET is required"):
        get_storage()


def test_get_storage_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "azure")

    with pytest.raises(ValueError, match="Unsupported STORAGE_BACKEND"):
        get_storage()
