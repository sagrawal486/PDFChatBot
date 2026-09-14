"""Tests for user-scoped persisted chunk retrieval."""

import pytest

from app.services.retrieval import UserChunkRetriever


class FakeChunkRepository:
    """Fake repository returning only the requested user's chunks."""

    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def get_chunks_for_user(self, user_id: int) -> list[tuple[str, list[float], int, int]]:
        """Record the owner filter and return deterministic chunks."""
        self.user_ids.append(user_id)
        return [
            ("database chunk", [1.0, 0.0], 1, 0),
            ("network chunk", [0.0, 1.0], 1, 1),
        ]


class FakeEmbeddingProvider:
    """Fake query embedding provider."""

    def embed(self, text: str) -> list[float]:
        """Return a deterministic query vector."""
        return [1.0, 0.0]


def test_user_chunk_retriever_filters_by_user_and_ranks_results() -> None:
    """Verify retrieval passes ownership to the repository and ranks matches."""
    repository = FakeChunkRepository()
    retriever = UserChunkRetriever(repository, FakeEmbeddingProvider())

    matches = retriever.search(user_id=7, query="database", limit=1)

    assert repository.user_ids == [7]
    assert matches[0].content == "database chunk"
    assert matches[0].score == pytest.approx(1.0)


def test_user_chunk_retriever_rejects_invalid_limit() -> None:
    """Verify retrieval requires a positive result limit."""
    retriever = UserChunkRetriever(
        FakeChunkRepository(),
        FakeEmbeddingProvider(),
    )

    with pytest.raises(ValueError, match="limit"):
        retriever.search(user_id=7, query="database", limit=0)