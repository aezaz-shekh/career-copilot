"""Tests for the /health endpoint.

The Ollama client is stubbed so these run fast and deterministically without a
model — SOW Section 9 (Integration tests with a stubbed LLM client).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.llm.client import OllamaDownError, find_missing_models
from app.main import app
from app.routers import health as health_router

client = TestClient(app)


def _stub_models(monkeypatch: pytest.MonkeyPatch, models: list[str]) -> None:
    """Make list_models() return a fixed inventory."""

    async def fake_list_models(timeout: float | None = None) -> list[str]:
        return models

    monkeypatch.setattr(health_router, "list_models", fake_list_models)


def test_health_ok_when_both_models_pulled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    _stub_models(
        monkeypatch,
        [settings.CHAT_MODEL, settings.QUESTION_MODEL, f"{settings.EMBED_MODEL}:latest"],
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"]["reachable"] is True
    assert body["models_missing"] == []


def test_health_degraded_when_ollama_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_models(timeout: float | None = None) -> list[str]:
        raise OllamaDownError(
            "Could not connect to Ollama",
            hint="Ollama is not running. Open a terminal and run: ollama serve",
        )

    monkeypatch.setattr(health_router, "list_models", fake_list_models)

    response = client.get("/health")

    # A down Ollama is a reported state, never an HTTP error.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ollama"]["reachable"] is False
    # The UI must get an actionable message, not a stack trace (SOW Section 7).
    assert "ollama serve" in body["ollama"]["hint"]


def test_health_degraded_when_chat_model_not_pulled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    _stub_models(monkeypatch, [f"{settings.EMBED_MODEL}:latest"])

    body = client.get("/health").json()

    assert body["status"] == "degraded"
    assert body["ollama"]["reachable"] is True
    assert settings.CHAT_MODEL in body["models_missing"]
    assert f"ollama pull {settings.CHAT_MODEL}" in body["ollama"]["hint"]


def test_untagged_model_matches_latest_tag() -> None:
    """`ollama pull nomic-embed-text` is listed as `nomic-embed-text:latest`."""
    assert find_missing_models(["nomic-embed-text"], ["nomic-embed-text:latest"]) == []
    assert find_missing_models(["llama3.2:3b"], ["llama3.2:1b"]) == ["llama3.2:3b"]


def test_root_banner() -> None:
    body = client.get("/").json()
    assert body["health"] == "/health"
