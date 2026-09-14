"""Retrieval-augmented answer generation contracts."""

from typing import Protocol

from app.services.embeddings import ChunkMatch
from app.services.retrieval import UserChunkRetriever


class ChatProvider(Protocol):
    """Generate an answer from a question and bounded document context."""

    def answer(self, question: str, context: str) -> str:
        """Return an answer grounded in the supplied context."""


class RagAnswer:
    """Answer text together with the retrieved supporting chunks."""

    def __init__(self, answer: str, citations: list[ChunkMatch]) -> None:
        """Create a response containing answer text and citations."""
        self.answer = answer
        self.citations = citations


class RagService:
    """Retrieve user-owned context and ask an injected chat provider."""

    def __init__(
        self,
        retriever: UserChunkRetriever,
        chat_provider: ChatProvider,
        max_context_characters: int = 8000,
    ) -> None:
        """Inject retrieval and generation collaborators with a context bound."""
        if max_context_characters <= 0:
            raise ValueError("max_context_characters must be greater than zero")
        self.retriever = retriever
        self.chat_provider = chat_provider
        self.max_context_characters = max_context_characters

    def answer(self, user_id: int, question: str, limit: int = 5) -> RagAnswer:
        """Return a bounded, user-scoped answer with retrieval citations."""
        if not question.strip():
            raise ValueError("question must not be empty")

        citations = self.retriever.search(user_id, question, limit)
        context_parts: list[str] = []
        context_length = 0
        for citation in citations:
            part = citation.content.strip()
            if context_length + len(part) > self.max_context_characters:
                break
            context_parts.append(part)
            context_length += len(part)

        context = "\n\n".join(context_parts)
        answer = self.chat_provider.answer(question, context)
        return RagAnswer(answer=answer, citations=citations[: len(context_parts)])