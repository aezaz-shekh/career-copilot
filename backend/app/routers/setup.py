"""First-run setup endpoints (Phase 4, Prompt 4.1).

Powers the setup wizard: one status probe covering Ollama, the required models,
and the optional voice binaries; plus a streaming model-pull so the wizard can
show a real progress bar (SOW deliverable D2 — auto-install with a visible
progress step).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import runtime_config
from app.config import get_settings
from app.llm.client import OllamaClient, OllamaError, find_missing_models, list_models
from app.services import stt, tts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


class PullRequest(BaseModel):
    model: str


@router.get("/status", summary="First-run readiness: Ollama, models, voice")
async def setup_status() -> dict:
    """One call the wizard can poll: what is ready and what still needs doing."""
    settings = get_settings()
    required = {
        "chat": runtime_config.get_active_chat_model(),
        "questions": settings.QUESTION_MODEL,
        "embed": settings.EMBED_MODEL,
    }

    reachable = True
    installed: list[str] = []
    try:
        installed = await list_models()
    except OllamaError as exc:
        reachable = False
        logger.info("Setup probe: Ollama unreachable — %s", exc.message)

    missing = (
        find_missing_models(list(required.values()), installed)
        if reachable
        else list(required.values())
    )

    return {
        "ollama": {"reachable": reachable, "url": settings.OLLAMA_URL},
        "models": {"required": required, "installed": installed, "missing": missing},
        "voice": {
            "stt_available": stt.stt_available(),
            "tts_available": tts.tts_available(),
            "configured": stt.stt_available() and tts.tts_available(),
        },
        "data_path": str(settings.DB_PATH),
        "ready": reachable and not missing,
    }


@router.post("/pull", summary="Download a model, streaming progress (SSE)")
async def pull_model(request: PullRequest) -> StreamingResponse:
    """Pull `request.model`, forwarding Ollama's download progress as SSE.

    Emits `progress` frames ({status, percent, completed, total}) as layers
    download, then a final `done`, or `error` with a fix hint.
    """
    client = OllamaClient()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for update in client.pull_stream(request.model):
                total = update.get("total")
                completed = update.get("completed")
                percent = (
                    round(completed / total * 100, 1)
                    if isinstance(total, int) and total and isinstance(completed, int)
                    else None
                )
                yield _sse(
                    "progress",
                    {
                        "status": update.get("status", ""),
                        "percent": percent,
                        "completed": completed,
                        "total": total,
                    },
                )
            yield _sse("done", {"model": request.model})
        except OllamaError as exc:
            logger.warning("Model pull failed: %s", exc.message)
            yield _sse("error", {"message": exc.message, "hint": exc.hint})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
