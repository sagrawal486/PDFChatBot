"""Embedding providers and similarity retrieval contracts."""

import json
import math
from typing import Any, Protocol

import boto3


class EmbeddingProvider(Protocol):
    """Create a numeric vector representation for text."""

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for the supplied text."""


class BedrockEmbeddingProvider:
    """Create embeddings through Amazon Bedrock Runtime."""

    def __init__(
        self,
        model_id: str,
        region: str,
        client: Any | None = None,
    ) -> None:
        """Configure Bedrock with an injectable client for deterministic tests."""
        self.model_id = model_id
        self.client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
        )

    def embed(self, text: str) -> list[float]:
        """Invoke the configured Bedrock embedding model for one text value."""
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        return payload["embedding"]


class ChunkMatch:
    """A retrieved chunk and its similarity score."""

    def __init__(self, content: str, score: float) -> None:
        self.content = content
        self.score = score


class InMemoryChunkRetriever:
    """Rank embedded chunks by cosine similarity without external services."""

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        """Inject the embedding provider used for query vectors."""
        self.embedding_provider = embedding_provider
        self._chunks: list[tuple[str, list[float]]] = []

    def add(self, content: str, embedding: list[float]) -> None:
        """Add an already-embedded chunk to the retrieval index."""
        if not embedding or not any(embedding):
            raise ValueError("embedding must contain a non-zero vector")
        self._chunks.append((content, embedding))

    def search(self, query: str, limit: int = 5) -> list[ChunkMatch]:
        """Return the highest-scoring chunks for a query."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        query_embedding = self.embedding_provider.embed(query)
        ranked = [
            ChunkMatch(content, _cosine_similarity(query_embedding, embedding))
            for content, embedding in self._chunks
        ]
        ranked.sort(key=lambda match: match.score, reverse=True)
        return ranked[:limit]


def _cosine_similarity(first: list[float], second: list[float]) -> float:
    """Return cosine similarity, rejecting vectors with incompatible sizes."""
    if len(first) != len(second):
        raise ValueError("embedding dimensions must match")

    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("embedding must contain a non-zero vector")

    return sum(left * right for left, right in zip(first, second)) / (
        first_norm * second_norm
    )