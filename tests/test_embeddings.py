"""Tests for embedding providers and similarity retrieval."""

import json
import threading
import time

import pytest

from app.services.embeddings import BedrockEmbeddingProvider, InMemoryChunkRetriever


class FakeBody:
    """Fake Bedrock response body."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        """Return a JSON response payload."""
        return json.dumps(self.payload).encode()


class FakeBedrockClient:
    """Fake Bedrock client recording model invocation details."""

    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs) -> dict:
        """Return a deterministic embedding response."""
        self.calls.append(kwargs)
        return {"body": FakeBody({"embedding": self.embedding})}


class ConcurrencyTrackingClient:
    """Fake Bedrock client that returns a text-derived vector and tracks overlap."""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def invoke_model(self, **kwargs) -> dict:
        """Simulate network latency while recording peak concurrent calls."""
        text = json.loads(kwargs["body"])["inputText"]
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        return {"body": FakeBody({"embedding": [float(len(text)), 0.0]})}


class FakeEmbeddingProvider:
    """Fake provider mapping query text to a vector."""

    def embed(self, text: str) -> list[float]:
        """Return a vector for retrieval tests."""
        return [1.0, 0.0] if text == "database" else [0.0, 1.0]


def test_bedrock_embedding_provider_invokes_configured_model() -> None:
    """Verify Bedrock model ID and input text are sent correctly."""
    client = FakeBedrockClient([0.2, 0.8])
    provider = BedrockEmbeddingProvider(
        model_id="test-model",
        region="eu-west-1",
        client=client,
    )

    embedding = provider.embed("hello")

    assert embedding == [0.2, 0.8]
    assert client.calls[0]["modelId"] == "test-model"
    assert json.loads(client.calls[0]["body"]) == {"inputText": "hello"}


def test_embed_batch_runs_calls_concurrently_and_preserves_order() -> None:
    """Verify batched embedding overlaps calls but returns vectors in input order."""
    client = ConcurrencyTrackingClient()
    provider = BedrockEmbeddingProvider(
        model_id="test-model",
        region="eu-west-1",
        client=client,
        max_concurrency=3,
    )

    vectors = provider.embed_batch(["a", "bb", "ccc", "dddd", "eeeee"])

    assert vectors == [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [4.0, 0.0], [5.0, 0.0]]
    assert 1 < client.max_active <= 3


def test_embed_batch_returns_empty_list_for_no_texts() -> None:
    """Verify batching short-circuits without contacting Bedrock."""
    client = ConcurrencyTrackingClient()
    provider = BedrockEmbeddingProvider(model_id="test-model", region="eu-west-1", client=client)

    assert provider.embed_batch([]) == []
    assert client.max_active == 0


def test_bedrock_provider_floors_max_concurrency_at_one() -> None:
    """Verify a non-positive concurrency setting is coerced to a safe minimum."""
    provider = BedrockEmbeddingProvider(
        model_id="test-model",
        region="eu-west-1",
        client=FakeBedrockClient([0.0]),
        max_concurrency=0,
    )

    assert provider.max_concurrency == 1


def test_in_memory_retriever_ranks_chunks_by_similarity() -> None:
    """Verify the most relevant embedded chunk is returned first."""
    retriever = InMemoryChunkRetriever(FakeEmbeddingProvider())
    retriever.add("database chunk", [1.0, 0.0])
    retriever.add("network chunk", [0.0, 1.0])

    matches = retriever.search("database", limit=1)

    assert len(matches) == 1
    assert matches[0].content == "database chunk"
    assert matches[0].score == pytest.approx(1.0)


def test_in_memory_retriever_rejects_invalid_limit() -> None:
    """Verify retrieval limits are bounded by a positive value."""
    retriever = InMemoryChunkRetriever(FakeEmbeddingProvider())

    with pytest.raises(ValueError, match="limit"):
        retriever.search("database", limit=0)