"""System health endpoint.

Answers one question for the UI: can this app do useful work right now?
That means the API is up, Ollama is reachable, and the required models are pulled.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.config import get_settings
from app.llm.client import OllamaError, find_missing_models, list_models
from app.schemas.health import HealthResponse, OllamaStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="System and local-AI status")
async def health() -> HealthResponse:
    """Report API, Ollama, and model-availability status.

    Always returns HTTP 200 — a down Ollama is a *reported state*, not a request
    failure, so the frontend badge can render it without error handling.
    """
    settings = get_settings()
    required = {
        "chat": settings.CHAT_MODEL,
        "questions": settings.QUESTION_MODEL,
        "embed": settings.EMBED_MODEL,
    }

    # Set only by the hosted deployment's shim; empty on a laptop.
    provider = settings.INFERENCE_PROVIDER.strip()
    mode = "hosted" if provider else "local"

    try:
        installed = await list_models()
    except OllamaError as exc:
        logger.warning("Ollama health probe failed: %s", exc.message)
        return HealthResponse(
            status="degraded",
            app=settings.APP_NAME,
            version=settings.APP_VERSION,
            inference_mode=mode,
            inference_provider=provider or None,
            ollama=OllamaStatus(
                reachable=False,
                url=settings.OLLAMA_URL,
                models_installed=[],
                error=exc.message,
                hint=exc.hint,
            ),
            models_required=required,
            models_missing=list(required.values()),
        )

    missing = find_missing_models(list(required.values()), installed)
    hint = None
    if missing:
        pulls = "  ".join(f"ollama pull {name}" for name in missing)
        hint = f"Download the missing model(s) once with: {pulls}"

    return HealthResponse(
        status="ok" if not missing else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        inference_mode=mode,
        inference_provider=provider or None,
        ollama=OllamaStatus(
            reachable=True,
            url=settings.OLLAMA_URL,
            models_installed=installed,
            hint=hint,
        ),
        models_required=required,
        models_missing=missing,
    )
