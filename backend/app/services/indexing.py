"""Auto-indexing glue: keep the vector store in sync with saved documents.

Called from the resume and JD routers right after a save. Kept in its own module
so the routers depend on a small, testable function rather than reaching into the
RAG pipeline directly.

Indexing failures are deliberately non-fatal. If Ollama is down when a resume is
saved, the resume must still be stored — losing the user's document because the
embedding model was unavailable would be a terrible trade. The document can
always be re-indexed later; a lost document cannot be recovered.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.llm.client import OllamaClient, OllamaError
from app.llm.rag import index_source
from app.models.base import SourceType

logger = logging.getLogger(__name__)


async def index_document(
    session: Session,
    source_type: SourceType,
    source_id: int,
    text: str,
    *,
    client: OllamaClient | None = None,
) -> int:
    """Index one document, swallowing embedding failures with a warning.

    Returns the number of chunks stored, or 0 if indexing could not run.
    """
    try:
        return await index_source(session, source_type, source_id, text, client=client)
    except OllamaError as exc:
        logger.warning(
            "Could not index %s:%s now (%s). It will need re-indexing.",
            source_type.value,
            source_id,
            exc.message,
        )
        session.rollback()
        return 0
