from fastapi import (
    APIRouter,
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
