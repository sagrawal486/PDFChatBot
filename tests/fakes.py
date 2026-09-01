from typing import Any

from fastapi import UploadFile


class MockS3Client:
    """
    Mock S3 client for testing S3Storage without AWS.
    Records all operations for verification.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []

    def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> dict[str, Any]:
        """
        Mock put_object call.
        Records the call and stores the object.
        """
        self.objects[Key] = Body
        self.put_calls.append(
            {
                "Bucket": Bucket,
                "Key": Key,
                "ContentType": ContentType,
                "Size": len(Body),
            }
        )
        return {"ETag": '"mock-etag"'}

    def delete_object(
        self,
        Bucket: str,
        Key: str,
    ) -> dict[str, Any]:
        """
        Mock delete_object call.
        Records the call and removes the object.
        """
        self.delete_calls.append(Key)
        if Key in self.objects:
            del self.objects[Key]
        return {"DeleteMarker": True}


class FakeStorage:
    """
    Fake storage for testing DocumentService.
    Does not actually store files.
    """

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
    """
    Storage that always fails to simulate error handling.
    """

    async def put(self, file: UploadFile) -> str:
        raise RuntimeError("storage unavailable")


class FakeRepository:
    """
    Fake repository for testing DocumentService.
    Records all created documents.
    """

    def __init__(self) -> None:
        self.created: list[Any] = []

    def create(self, document: Any) -> Any:
        self.created.append(document)
        return document