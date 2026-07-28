"""Response schemas for the /health endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OllamaStatus(BaseModel):
    """Liveness and model inventory of the local Ollama runtime."""

    reachable: bool = Field(description="True if Ollama answered /api/tags in time")
    url: str = Field(description="Base URL the backend probed")
    models_installed: list[str] = Field(
        default_factory=list, description="All models currently pulled locally"
    )
    error: str | None = Field(default=None, description="Technical reason, for logs")
    hint: str | None = Field(default=None, description="Plain-language fix, for the UI")


class HealthResponse(BaseModel):
    """Overall system readiness.

    `status` is "ok" only when the API is up, Ollama is reachable, *and* both
    required models are pulled — i.e. the app can actually do useful work.
    """

    status: Literal["ok", "degraded"]
    app: str
    version: str
    ollama: OllamaStatus
    models_required: dict[str, str] = Field(
        description="Role -> model name, e.g. {'chat': 'llama3.2:3b'}"
    )
    models_missing: list[str] = Field(
        default_factory=list, description="Required models not yet pulled"
    )
