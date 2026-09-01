"""
Tests for S3Storage adapter.

These tests verify that S3Storage correctly implements the Storage protocol
without connecting to real AWS. A mocked S3 client is used.
"""

import asyncio
from io import BytesIO

from fastapi import UploadFile

from app.services.s3_storage import S3Storage
from tests.fakes import MockS3Client


def make_upload(
    filename: str = "document.pdf",
    content: bytes = b"%PDF-test content",
    content_type: str = "application/pdf",
) -> UploadFile:
    """
    Create a test UploadFile.

    Args:
        filename: Name of the uploaded file
        content: File contents
        content_type: MIME type

    Returns:
        UploadFile ready for testing
    """
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


def test_s3_storage_put_uploads_to_s3() -> None:
    """
    Verify that S3Storage.put() calls the S3 client with correct parameters.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)
    upload = make_upload(filename="my-file.pdf", content=b"%PDF-test")

    storage_key = asyncio.run(storage.put(upload))

    assert storage_key == "my-file.pdf"
    assert len(mock_client.put_calls) == 1
    put_call = mock_client.put_calls[0]
    assert put_call["Bucket"] == "test-bucket"
    assert put_call["Key"] == "my-file.pdf"
    assert put_call["ContentType"] == "application/pdf"
    assert put_call["Size"] == len(b"%PDF-test")


def test_s3_storage_put_stores_file_bytes() -> None:
    """
    Verify that S3Storage.put() stores the complete file contents.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)
    content = b"%PDF-1.7\nstream data\nendstream"
    upload = make_upload(content=content)

    asyncio.run(storage.put(upload))

    assert mock_client.objects["document.pdf"] == content


def test_s3_storage_put_uses_content_type_from_file() -> None:
    """
    Verify that S3Storage.put() sends the validated content type to S3.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)
    upload = make_upload(content_type="application/pdf")

    asyncio.run(storage.put(upload))

    assert mock_client.put_calls[0]["ContentType"] == "application/pdf"


def test_s3_storage_delete_removes_from_s3() -> None:
    """
    Verify that S3Storage.delete() calls the S3 client to remove an object.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)

    asyncio.run(storage.delete("some-key.pdf"))

    assert len(mock_client.delete_calls) == 1
    assert mock_client.delete_calls[0] == "some-key.pdf"


def test_s3_storage_delete_removes_object_from_mock_store() -> None:
    """
    Verify that S3Storage.delete() actually removes stored objects.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)
    upload = make_upload(filename="to-delete.pdf")

    # First upload a file
    asyncio.run(storage.put(upload))
    assert "to-delete.pdf" in mock_client.objects

    # Then delete it
    asyncio.run(storage.delete("to-delete.pdf"))
    assert "to-delete.pdf" not in mock_client.objects


def test_s3_storage_works_with_different_bucket_names() -> None:
    """
    Verify that S3Storage can be configured with different bucket names.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="production-bucket", client=mock_client)
    upload = make_upload()

    asyncio.run(storage.put(upload))

    assert mock_client.put_calls[0]["Bucket"] == "production-bucket"


def test_s3_storage_handles_multiple_files() -> None:
    """
    Verify that S3Storage correctly handles multiple uploads.
    """
    mock_client = MockS3Client()
    storage = S3Storage(bucket="test-bucket", client=mock_client)

    upload1 = make_upload(filename="file1.pdf", content=b"%PDF-first")
    upload2 = make_upload(filename="file2.pdf", content=b"%PDF-second")

    asyncio.run(storage.put(upload1))
    asyncio.run(storage.put(upload2))

    assert len(mock_client.objects) == 2
    assert mock_client.objects["file1.pdf"] == b"%PDF-first"
    assert mock_client.objects["file2.pdf"] == b"%PDF-second"
