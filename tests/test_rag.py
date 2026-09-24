"""Tests for bounded retrieval-augmented answer generation."""

import pytest

from app.services.rag import RagService
from app.services.retrieval import UserChunkRetriever


class FakeRepository:
    """Fake user-scoped chunk repository."""

    def search_similar_chunks(self, user_id: int, query_embedding: list[float], limit: int):
        """Return deterministic chunks with citation metadata."""
        return [("The answer is forty-two.", 1.0, 8, 2, 5)]


class FakeEmbeddingProvider:
    """Fake query embedding provider."""

    def embed(self, text: str) -> list[float]:
        """Return a deterministic query vector."""
        return [1.0, 0.0]


class FakeChatProvider:
    """Fake chat provider recording the bounded context."""

    def __init__(self) -> None:
        self.questions: list[str] = []
        self.contexts: list[str] = []

    def answer(self, question: str, context: str) -> str:
        """Return a deterministic answer."""
        self.questions.append(question)
        self.contexts.append(context)
        return "The answer is forty-two."


def test_rag_service_answers_with_retrieved_context_and_citation() -> None:
    """Verify context reaches the chat provider and citation is returned."""
    chat_provider = FakeChatProvider()
    service = RagService(
        retriever=UserChunkRetriever(FakeRepository(), FakeEmbeddingProvider()),
        chat_provider=chat_provider,
    )

    result = service.answer(user_id=7, question="What is the answer?")

    assert result.answer == "The answer is forty-two."
    assert result.citations[0].document_id == 8
    assert result.citations[0].chunk_index == 2
    assert result.citations[0].page_number == 5
    assert chat_provider.questions == ["What is the answer?"]
    assert chat_provider.contexts == ["The answer is forty-two."]


def test_rag_service_rejects_empty_questions() -> None:
    """Verify empty questions are rejected before retrieval or generation."""
    service = RagService(
        retriever=UserChunkRetriever(FakeRepository(), FakeEmbeddingProvider()),
        chat_provider=FakeChatProvider(),
    )

    with pytest.raises(ValueError, match="question"):
        service.answer(user_id=7, question=" ")