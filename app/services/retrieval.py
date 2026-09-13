"""User-scoped retrieval over persisted document chunk embeddings."""

from typing import Protocol

from app.services.embeddings import ChunkMatch, EmbeddingProvider, _cosine_similarity


class ChunkRepository(Protocol):
    """Persistence boundary required by the retrieval service."""

    def get_chunks_for_user(self, user_id: int) -> list[tuple[str, list[float]]]:
        """Return embedded chunks for one user."""


class UserChunkRetriever:
    """Retrieve relevant chunks while enforcing user ownership at the query boundary."""

    def __init__(
        self,
        repository: ChunkRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        """Inject persistence and query embedding collaborators."""
        self.repository = repository
        self.embedding_provider = embedding_provider

    def search(self, user_id: int, query: str, limit: int = 5) -> list[ChunkMatch]:
        """Return the highest-scoring chunks owned by the requested user."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        query_embedding = self.embedding_provider.embed(query)
        matches = [
            ChunkMatch(content, _cosine_similarity(query_embedding, embedding))
            for content, embedding in self.repository.get_chunks_for_user(user_id)
        ]
        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:limit]