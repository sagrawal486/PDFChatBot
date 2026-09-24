from pydantic import BaseModel


class CitationResponse(BaseModel):
    """One supporting chunk behind an answer, with enough detail to locate it."""

    document_id: int
    chunk_index: int
    page_number: int | None = None
    score: float
    excerpt: str


class QuestionResponse(BaseModel):
    """An answer grounded in the caller's own documents, with its citations."""

    answer: str
    citations: list[CitationResponse]
