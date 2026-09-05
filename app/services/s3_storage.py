"""
AWS S3 storage adapter.

This module provides an S3Storage implementation of the Storage protocol.
It uses boto3 to interact with AWS S3.

The client is injected to allow easy testing with mocked clients.
"""

from typing import Any
from uuid import uuid4

import boto3
from fastapi import UploadFile


class S3Storage:
    """
    S3 storage implementation behind the Storage protocol.

    This adapter talks to AWS S3 using a boto3 client.
    The client is injected, making it easy to test with mocks.
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        client: Any | None = None,
    ) -> None:
        """
        Initialize S3Storage.

        Args:
            bucket: S3 bucket name (e.g., "my-app-pdfs")
            region: AWS region used when creating the default client
            client: boto3 S3 client or mock client for testing
        """
        self.bucket = bucket
        self.client = client or boto3.client("s3", region_name=region)

    async def put(self, file: UploadFile) -> str:
        """
        Upload a file to S3 and return the storage key.

        Args:
            file: FastAPI UploadFile with validated PDF content

        Returns:
            The S3 object key (file name in the bucket)

        Raises:
            Exception: If S3 upload fails
        """
        # Read the complete file into memory.
        # In production with large files, use multipart upload.
        file_bytes = await file.read()

        storage_key = f"{uuid4().hex}.pdf"

        # Call S3 to upload the object.
        # The Content-Type was validated by DocumentService.
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=file_bytes,
            ContentType=file.content_type or "application/pdf",
        )

        return storage_key

    async def delete(self, storage_key: str) -> None:
        """
        Delete a file from S3 by its key.

        Args:
            storage_key: The S3 object key to delete
        """
        self.client.delete_object(
            Bucket=self.bucket,
            Key=storage_key,
        )

    async def get(self, storage_key: str) -> bytes:
        """Download an S3 object and return its bytes for PDF processing."""
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=storage_key,
        )
        return response["Body"].read()
