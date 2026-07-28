"""Text chunk metadata for the RAG pipeline (SOW Section 6.2).

Storage is deliberately split across two tables:

- `embedding_chunks` (this ORM model) holds the human-readable metadata and the
  chunk text.
- `vec_embedding_chunks` is a sqlite-vec **virtual table** holding only the
  float vectors, created in `app/db.py`. Virtual tables cannot be described by
  the SQLAlchemy ORM, and the vector itself is never read directly — it is only
  ever matched against. The two share a primary key, so a similarity search
  returns chunk ids that join straight back to this table.

`source_type` + `source_id` is a deliberate polymorphic reference rather than a
foreign key, because a chunk can come from either a resume or a job description.
Referential integrity is enforced in the service layer on delete.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SourceType, enum_column, utcnow


class EmbeddingChunk(Base):
    """One chunk of source text whose vector lives in the sqlite-vec table."""

    __tablename__ = "embedding_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Position of this chunk within its source document, so retrieved context
    # can be re-assembled in reading order.
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Retrieval and deletion both filter on (source_type, source_id).
    __table_args__ = (Index("ix_embedding_chunks_source", "source_type", "source_id"),)

    def __repr__(self) -> str:
        return f"<EmbeddingChunk id={self.id} {self.source_type.value}:{self.source_id}>"
