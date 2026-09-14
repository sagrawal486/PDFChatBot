from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.settings import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.services.chat_provider import get_chat_provider
from app.services.embeddings import BedrockEmbeddingProvider
from app.services.rag import RagService
from app.services.retrieval import UserChunkRetriever


router = APIRouter(prefix="/questions", tags=["Questions"])


class QuestionRequest(BaseModel):
    question: str


def get_rag_service(db: Session = Depends(get_db)) -> RagService:
    repository = DocumentRepository(db)
    embedding_provider = BedrockEmbeddingProvider(
        model_id=settings.EMBEDDING_MODEL_ID,
        region=settings.AWS_REGION,
    )
    retriever = UserChunkRetriever(repository, embedding_provider)
    return RagService(
        retriever=retriever,
        chat_provider=get_chat_provider(),
    )


@router.post("", status_code=status.HTTP_200_OK)
async def ask_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    service: RagService = Depends(get_rag_service),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")

    return service.answer(current_user.id, request.question)
