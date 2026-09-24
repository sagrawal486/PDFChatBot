"""Regression tests for embedding (de)serialization against the real pgvector type.

These exist because DocumentRepository was previously detecting pgvector by comparing
DocumentChunk.__table__.c.embedding.type.__class__.__name__ to the string "Vector" --
but pgvector's real SQLAlchemy class is named "VECTOR", so that check always failed,
silently falling back to JSON-string storage. pgvector's own bind processor then tried
to numpy-parse that JSON string as a single float and crashed with:
    ValueError: could not convert string to float: '[-0.045, ...]'
None of the fake-repository tests elsewhere in this suite exercise the real
DocumentRepository, so this bug had no coverage. These tests use the real classes
(no fakes) to make sure that gap doesn't reopen.
"""

from app.models.document_chunk import USES_PGVECTOR
from app.repositories.document_repository import DocumentRepository


def test_pgvector_is_active_in_this_environment() -> None:
    """Guard the assumption the other tests here rely on: pgvector is installed and
    enabled, so serialization must use the vector-native path, not the JSON fallback."""
    assert USES_PGVECTOR is True


def test_serialize_embedding_returns_a_raw_list_when_pgvector_is_active() -> None:
    """Verify embeddings are handed to pgvector as a list, never a JSON string.

    pgvector's own Vector bind processor expects a list/ndarray; a JSON string
    causes numpy to try converting the whole string to one float and crash.
    """
    serialized = DocumentRepository._serialize_embedding([0.1, -0.2, 0.3])

    assert serialized == [0.1, -0.2, 0.3]
    assert isinstance(serialized, list)


def test_deserialize_embedding_round_trips_a_raw_list() -> None:
    """Verify reading a pgvector-native value back returns a plain list of floats."""
    assert DocumentRepository._deserialize_embedding([0.1, -0.2, 0.3]) == [0.1, -0.2, 0.3]


def test_deserialize_embedding_still_reads_legacy_json_strings() -> None:
    """Verify rows written before pgvector was enabled (JSON text) still load."""
    assert DocumentRepository._deserialize_embedding("[0.1, -0.2, 0.3]") == [0.1, -0.2, 0.3]
