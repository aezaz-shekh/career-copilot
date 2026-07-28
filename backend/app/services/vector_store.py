"""Read/write access to the sqlite-vec vector table.

The vector table is a virtual table, so it sits outside the ORM. Keeping every
statement that touches it in this one module means the rest of the codebase can
work with `EmbeddingChunk` rows and never think about vector serialisation.

All SQL here is parameterised (SOW Section 7, Privacy/Security).
"""

from __future__ import annotations

import logging
import struct
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import VEC_TABLE
from app.models.base import SourceType
from app.models.embedding import EmbeddingChunk

logger = logging.getLogger(__name__)


def serialize_vector(vector: Sequence[float]) -> bytes:
    """Pack a float list into the little-endian float32 blob sqlite-vec expects."""
    settings = get_settings()
    if len(vector) != settings.EMBED_DIM:
        raise ValueError(
            f"Expected a {settings.EMBED_DIM}-dimension vector from "
            f"{settings.EMBED_MODEL}, got {len(vector)}"
        )
    return struct.pack(f"{len(vector)}f", *vector)


def add_chunk(
    session: Session,
    *,
    source_type: SourceType,
    source_id: int,
    chunk_index: int,
    chunk_text: str,
    embedding: Sequence[float],
) -> EmbeddingChunk:
    """Store one chunk's text and its vector, keyed by the same id."""
    chunk = EmbeddingChunk(
        source_type=source_type,
        source_id=source_id,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
    )
    session.add(chunk)
    # Flush so the autoincrement id exists before the vector row references it.
    session.flush()

    session.execute(
        text(f"INSERT INTO {VEC_TABLE}(chunk_id, embedding) VALUES (:chunk_id, :embedding)"),
        {"chunk_id": chunk.id, "embedding": serialize_vector(embedding)},
    )
    return chunk


def search(
    session: Session,
    query_embedding: Sequence[float],
    *,
    k: int = 5,
    source_type: SourceType | None = None,
    source_id: int | None = None,
) -> list[tuple[EmbeddingChunk, float]]:
    """Return the `k` nearest chunks to `query_embedding`, closest first.

    Args:
        source_type / source_id: optional filter, so a resume critique retrieves
            only from that resume rather than from everything ever uploaded.

    Returns:
        (chunk, distance) pairs. Smaller distance means more similar.
    """
    # sqlite-vec resolves KNN inside the MATCH, so the filter is applied after
    # retrieval. Over-fetch when filtering, or a filtered search can come back
    # short.
    fetch_k = k * 4 if (source_type is not None or source_id is not None) else k

    rows = session.execute(
        text(
            f"SELECT chunk_id, distance FROM {VEC_TABLE} "
            f"WHERE embedding MATCH :embedding AND k = :k ORDER BY distance"
        ),
        {"embedding": serialize_vector(query_embedding), "k": fetch_k},
    ).all()

    if not rows:
        return []

    distances = {int(chunk_id): float(distance) for chunk_id, distance in rows}
    chunks = session.query(EmbeddingChunk).filter(EmbeddingChunk.id.in_(distances)).all()

    if source_type is not None:
        chunks = [c for c in chunks if c.source_type == source_type]
    if source_id is not None:
        chunks = [c for c in chunks if c.source_id == source_id]

    results = [(chunk, distances[chunk.id]) for chunk in chunks]
    results.sort(key=lambda pair: pair[1])
    return results[:k]


def delete_for_source(session: Session, source_type: SourceType, source_id: int) -> int:
    """Remove every chunk (and its vector) for one source document.

    The virtual table has no foreign key to cascade through, so its rows must be
    deleted explicitly — otherwise "Delete all my data" (SOW Section 7) would
    leave orphaned vectors behind.
    """
    chunk_ids = [
        row[0]
        for row in session.query(EmbeddingChunk.id)
        .filter(
            EmbeddingChunk.source_type == source_type,
            EmbeddingChunk.source_id == source_id,
        )
        .all()
    ]
    if not chunk_ids:
        return 0

    for chunk_id in chunk_ids:
        session.execute(
            text(f"DELETE FROM {VEC_TABLE} WHERE chunk_id = :chunk_id"),
            {"chunk_id": chunk_id},
        )
    session.query(EmbeddingChunk).filter(EmbeddingChunk.id.in_(chunk_ids)).delete(
        synchronize_session=False
    )
    return len(chunk_ids)
