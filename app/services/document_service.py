from fastapi import HTTPException, UploadFile

from app.core.settings import settings
from app.models.document import Document
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_dispatcher import DocumentDispatcher
from app.services.storage import Storage


class DocumentService:

    PDF_SIGNATURE = b"%PDF-"
    READ_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        repository: DocumentRepository,
        storage: Storage,
        dispatcher: DocumentDispatcher | None = None,
    ):
        self.repository = repository
        self.storage = storage
        self.dispatcher = dispatcher

    async def upload(self,file: UploadFile,user_id: int,    ):

        if file.content_type != "application/pdf":

            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed",
            )

        file_size = await self._validate_file(file)
        storage_key = await self.storage.put(file)

        document = Document(
            user_id=user_id,
            file_name=file.filename,
            storage_key=storage_key,
            content_type=file.content_type,
            file_size=file_size,
            status="uploaded",
        )

        created_document = self.repository.create(document)
        if self.dispatcher is not None:
            self.dispatcher.enqueue(created_document.id)

        return created_document

    async def _validate_file(self, file: UploadFile) -> int:
        maximum_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        file_size = 0
        signature = b""

        file.file.seek(0)

        while chunk := await file.read(self.READ_CHUNK_SIZE):
            file_size += len(chunk)

            if len(signature) < len(self.PDF_SIGNATURE):
                remaining_signature_bytes = len(self.PDF_SIGNATURE) - len(signature)
                signature += chunk[:remaining_signature_bytes]

            if file_size > maximum_size:
                raise HTTPException(
                    status_code=400,
                    detail="File size exceeds the maximum allowed size",
                )

        file.file.seek(0)

        if signature != self.PDF_SIGNATURE:
            raise HTTPException(
                status_code=400,
                detail="PDF file is invalid",
            )

        return file_size
