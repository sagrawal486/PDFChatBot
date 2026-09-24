"""User-scoped retrieval over persisted document chunk embeddings."""

from typing import Protocol

from app.services.embeddings import ChunkMatch, EmbeddingProvider


class ChunkRepository(Protocol):
    """Persistence boundary required by the retrieval service."""

    def search_similar_chunks(
        self,
        user_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[tuple[str, float, int, int, int | None]]:
        """Return (content, score, document_id, chunk_index, page_number) for the closest
        user-owned chunks."""


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
        rows = self.repository.search_similar_chunks(user_id, query_embedding, limit)
        return [
            ChunkMatch(
                content,
                score,
                document_id=document_id,
                chunk_index=chunk_index,
                page_number=page_number,
            )
            for content, score, document_id, chunk_index, page_number in rows
        ]
