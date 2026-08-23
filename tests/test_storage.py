import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from app.services.storage import LocalStorage


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
