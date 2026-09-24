import json

from app.models.document import Document
from app.models.document_chunk import USES_PGVECTOR, DocumentChunk
from app.repositories.base import BaseRepository
from app.services.embeddings import cosine_similarity


class DocumentRepository(
    BaseRepository[Document]
):

    model = Document

    @staticmethod
    def _serialize_embedding(embedding: list[float]) -> list[float] | str:
        """Store embeddings in vector form when available, otherwise keep JSON compatibility."""
        flattened = list(embedding)
        if USES_PGVECTOR:
            return flattened
        return json.dumps(flattened)

    @staticmethod
    def _deserialize_embedding(value: list[float] | str) -> list[float]:
        """Read embedded vectors from pgvector or legacy JSON storage."""
        if isinstance(value, str):
            return json.loads(value)
        return list(value)

    def mark_status(self, document: Document, status: str) -> Document:
        """Update and persist a document processing status."""
        document.status = status
        self.db.commit()
        self.db.refresh(document)
        return document

    def replace_chunks(self, document_id: int, chunks: list[tuple[int, str]]) -> list[DocumentChunk]:
        """Replace a document's extracted (page_number, content) chunks in stable order."""
        existing_chunks = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        for chunk in existing_chunks:
            self.db.delete(chunk)

        new_chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                page_number=page_number,
                content=content,
            )
            for index, (page_number, content) in enumerate(chunks)
        ]
        self.db.add_all(new_chunks)
        self.db.commit()
        return new_chunks

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[int, str, list[float]]],
    ) -> list[DocumentChunk]:
        """Replace (page_number, content, embedding) chunks in vector-ready form."""
        existing_chunks = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        for chunk in existing_chunks:
            self.db.delete(chunk)

        new_chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                page_number=page_number,
                content=content,
                embedding=self._serialize_embedding(embedding),
            )
            for index, (page_number, content, embedding) in enumerate(chunks)
        ]
        self.db.add_all(new_chunks)
        self.db.commit()
        return new_chunks

    def search_similar_chunks(
        self,
        user_id: int,
        query_embedding: list[float],
        limit: int,
    ) -> list[tuple[str, float, int, int, int | None]]:
        """Return the closest chunks owned by a user as
        (content, score, document_id, chunk_index, page_number)."""
        base = self.db.query(DocumentChunk).join(
            Document,
            Document.id == DocumentChunk.document_id,
        ).filter(
            Document.user_id == user_id,
            DocumentChunk.embedding.is_not(None),
        )

        if USES_PGVECTOR:
            distance = DocumentChunk.embedding.cosine_distance(query_embedding)
            rows = base.add_columns(distance.label("distance")).order_by(distance).limit(limit).all()
            return [
                (chunk.content, 1.0 - float(dist), chunk.document_id, chunk.chunk_index, chunk.page_number)
                for chunk, dist in rows
            ]

        scored = [
            (
                row.content,
                cosine_similarity(query_embedding, self._deserialize_embedding(row.embedding)),
                row.document_id,
                row.chunk_index,
                row.page_number,
            )
            for row in base.all()
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def list_for_user(self, user_id: int) -> list[Document]:
        """Return a user's documents, newest first."""
        return (
            self.db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .all()
        )

    def get_for_user(self, document_id: int, user_id: int) -> Document | None:
        """Return a document only if it belongs to the user."""
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )
