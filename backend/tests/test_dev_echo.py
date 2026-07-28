"""Tests for POST /api/dev/echo-llm — the end-to-end streaming smoke endpoint.

The client's streaming method is replaced with a stub, so these verify the SSE
wire format and the error path without needing Ollama.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.llm.client import OllamaClient, OllamaDownError
from app.main import app

client = TestClient(app)


def test_echo_streams_tokens_as_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(self, messages, **kwargs) -> AsyncIterator[str]:
        assert messages == [{"role": "user", "content": "say hi"}]
        for token in ["Hello", " there"]:
            yield token

    monkeypatch.setattr(OllamaClient, "chat_stream", fake_stream)

    response = client.post("/api/dev/echo-llm", json={"message": "say hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert 'event: token\ndata: {"text": "Hello"}' in body
    assert 'event: token\ndata: {"text": " there"}' in body
    assert "event: done" in body


def test_echo_reports_ollama_down_as_an_sse_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Headers are already sent when generation fails, so errors ride the stream."""

    async def failing_stream(self, messages, **kwargs) -> AsyncIterator[str]:
        raise OllamaDownError(
            "Could not connect to Ollama",
            hint="Ollama is not running. Open a terminal and run: ollama serve",
        )
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(OllamaClient, "chat_stream", failing_stream)

    response = client.post("/api/dev/echo-llm", json={"message": "say hi"})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "ollama serve" in response.text


def test_echo_preserves_newlines_in_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raw newline in a token would otherwise be read as an SSE frame break."""

    async def fake_stream(self, messages, **kwargs) -> AsyncIterator[str]:
        yield "line one\nline two"

    monkeypatch.setattr(OllamaClient, "chat_stream", fake_stream)

    body = client.post("/api/dev/echo-llm", json={"message": "hi"}).text

    # JSON-encoded, so the newline travels as the two characters \ and n.
    assert 'data: {"text": "line one\\nline two"}' in body
    assert body.count("event: token") == 1


def test_echo_rejects_empty_message() -> None:
    assert client.post("/api/dev/echo-llm", json={"message": ""}).status_code == 422


def test_echo_rejects_out_of_range_temperature() -> None:
    response = client.post("/api/dev/echo-llm", json={"message": "hi", "temperature": 5})
    assert response.status_code == 422
