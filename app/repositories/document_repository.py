from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.repositories.base import BaseRepository


class DocumentRepository(
    BaseRepository[Document]
):

    model = Document

    def mark_status(self, document: Document, status: str) -> Document:
        """Update and persist a document processing status."""
        document.status = status
        self.db.commit()
        self.db.refresh(document)
        return document

    def replace_chunks(self, document_id: int, chunks: list[str]) -> list[DocumentChunk]:
        """Replace a document's extracted chunks in their stable order."""
        existing_chunks = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        for chunk in existing_chunks:
            self.db.delete(chunk)

        new_chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                content=content,
            )
            for index, content in enumerate(chunks)
        ]
        self.db.add_all(new_chunks)
        self.db.commit()
        return new_chunks

    def replace_chunks_with_embeddings(
        self,
        document_id: int,
        chunks: list[tuple[str, list[float]]],
    ) -> list[DocumentChunk]:
        """Replace chunks and persist each embedding as JSON text."""
        existing_chunks = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        for chunk in existing_chunks:
            self.db.delete(chunk)

        import json

        new_chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                content=content,
                embedding=json.dumps(embedding),
            )
            for index, (content, embedding) in enumerate(chunks)
        ]
        self.db.add_all(new_chunks)
        self.db.commit()
        return new_chunks
    