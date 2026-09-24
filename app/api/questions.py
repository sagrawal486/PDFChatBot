from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.settings import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.question_log_repository import QuestionLogRepository
from app.schemas.question import CitationResponse, QuestionResponse
from app.services.chat_provider import get_chat_provider
from app.services.embeddings import BedrockEmbeddingProvider
from app.services.rag import RagService
from app.services.retrieval import UserChunkRetriever
from app.services.usage_limiter import DailyQuestionLimiter, UsageLimitExceeded

EXCERPT_MAX_CHARS = 500


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


def get_usage_limiter(db: Session = Depends(get_db)) -> DailyQuestionLimiter:
    return DailyQuestionLimiter(
        repository=QuestionLogRepository(db),
        max_per_day=settings.MAX_QUESTIONS_PER_DAY,
    )


@router.post("", status_code=status.HTTP_200_OK, response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    service: RagService = Depends(get_rag_service),
    limiter: DailyQuestionLimiter = Depends(get_usage_limiter),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")

    try:
        limiter.ensure_within_limit(current_user.id)
    except UsageLimitExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error

    result = service.answer(current_user.id, request.question)
    limiter.record(current_user.id)

    return QuestionResponse(
        answer=result.answer,
        citations=[
            CitationResponse(
                document_id=citation.document_id,
                chunk_index=citation.chunk_index,
                page_number=citation.page_number,
                score=citation.score,
                excerpt=citation.content[:EXCERPT_MAX_CHARS],
            )
            for citation in result.citations
        ],
    )
