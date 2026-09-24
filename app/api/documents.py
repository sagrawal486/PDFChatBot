from fastapi import (
    APIRouter,
    Response,
    Depends,
    File,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
)
from app.db.session import get_db
from app.models.user import User
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    DocumentService,
)
from app.services.document_dispatcher import CeleryDocumentDispatcher
from app.services.storage import Storage, get_storage


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


def get_document_service(
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
):

    repository = DocumentRepository(db)

    return DocumentService(
        repository,
        storage,
        CeleryDocumentDispatcher(),
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(
        get_current_user
    ),
    service: DocumentService = Depends(
        get_document_service
    ),
):

    return await service.upload(
        file,
        current_user.id,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.list_documents(current_user.id)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.get_document(document_id, current_user.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    await service.delete_document(document_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
