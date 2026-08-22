from fastapi import HTTPException, UploadFile

from app.core.settings import settings
from app.models.document import Document
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.file_storage import save_file


class DocumentService:

    def __init__(self,repository: DocumentRepository,):
        self.repository = repository

    async def upload(self,file: UploadFile,user_id: int,    ):

        if file.content_type != "application/pdf":

            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed",
            )

        file_path = await save_file(file)

        document = Document(
            user_id=user_id,
            file_name=file.filename,
            file_path=file_path,
            status="uploaded",
        )

        return self.repository.create(
            document
        )
