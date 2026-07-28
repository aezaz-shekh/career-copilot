"""Development-only diagnostic endpoints.

`POST /api/dev/echo-llm` streams a reply straight from the local model. It exists
to prove the whole chain end to end — browser -> FastAPI -> Ollama -> back as
Server-Sent Events — which is the Phase 0 exit criterion ("streaming 'hello' from
local model to browser UI"). Feature modules use the same streaming machinery.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.llm import rag
from app.llm.client import OllamaClient, OllamaError
from app.models.base import SourceType
from app.schemas.dev import EchoRequest, RagTestResponse, RetrievedChunkOut
from app.services import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev", tags=["dev"])


def sse_event(event: str, payload: dict[str, Any]) -> str:
    """Format one Server-Sent Event frame.

    The wire format is `event: <name>` then `data: <json>` then a blank line.
    JSON-encoding the payload keeps newlines inside tokens from being read as
    frame separators — a subtle bug that only shows up on multi-line replies.
    """
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post(
    "/echo-llm",
    summary="Stream a reply from the local model (Server-Sent Events)",
    response_class=StreamingResponse,
)
async def echo_llm(request: EchoRequest) -> StreamingResponse:
    """Send `request.message` to the model and stream the reply token by token.

    Emits three event types:
      - `token` — `{"text": "..."}` for each generated fragment
      - `done`  — `{}` once generation finishes
      - `error` — `{"message": ..., "hint": ...}` if anything goes wrong

    Errors arrive as an SSE event rather than an HTTP error status, because the
    response headers are already sent by the time generation can fail.
    """
    client = OllamaClient()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for token in client.chat_stream(
                [{"role": "user", "content": request.message}],
                model=request.model,
                temperature=request.temperature,
                num_predict=request.num_predict,
                keep_alive="10m",
            ):
                yield sse_event("token", {"text": token})
            yield sse_event("done", {})
        except OllamaError as exc:
            logger.warning("echo-llm stream failed: %s", exc.message)
            yield sse_event("error", {"message": exc.message, "hint": exc.hint})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # stops any proxy from buffering the stream
        },
    )


@router.get(
    "/rag-test",
    response_model=RagTestResponse,
    summary="Retrieve chunks for a query, to eyeball relevance",
)
async def rag_test(
    q: str = Query(min_length=1, description="A natural-language query to retrieve against"),
    resume_id: int | None = Query(default=None, description="Restrict to this resume"),
    jd_id: int | None = Query(default=None, description="Restrict to this job description"),
    top_k: int = Query(default=6, ge=1, le=20),
    session: Session = Depends(get_session),
) -> RagTestResponse:
    """Show what retrieval returns for a query, so relevance can be judged by eye.

    This is the manual verification tool for the RAG pipeline: type a question,
    see which chunks come back and their similarity scores, and confirm the
    right passages surface before any of this is wired into a real feature.
    """
    total_chunks = session.query(vector_store.EmbeddingChunk).count()
    if total_chunks == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Nothing has been indexed yet",
                "hint": "Save a resume or a job description first, then try again.",
            },
        )

    source_ids: dict[SourceType, int] = {}
    if resume_id is not None:
        source_ids[SourceType.RESUME] = resume_id
    if jd_id is not None:
        source_ids[SourceType.JD] = jd_id

    try:
        chunks = await rag.retrieve(session, q, source_ids=source_ids or None, top_k=top_k)
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc

    return RagTestResponse(
        query=q,
        indexed_chunks=total_chunks,
        returned=len(chunks),
        results=[
            RetrievedChunkOut(
                source_type=chunk.source_type.value,
                source_id=chunk.source_id,
                chunk_index=chunk.chunk_index,
                similarity=chunk.similarity,
                distance=round(chunk.distance, 4),
                text=chunk.text,
            )
            for chunk in chunks
        ],
    )
