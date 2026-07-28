"""Tests for the Ollama client wrapper.

Every test drives the real client code against an `httpx.MockTransport`, so the
whole suite runs with no Ollama installed and no model pulled — SOW Section 9
("integration tests with a stubbed LLM client, so tests run fast and
deterministically without a model").
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.llm.client import (
    GenerationError,
    ModelMissingError,
    OllamaClient,
    OllamaDownError,
    find_missing_models,
    normalise_model_name,
)


class Score(BaseModel):
    """Minimal stand-in for a real scoring schema."""

    score: int
    comment: str


def make_client(handler) -> OllamaClient:
    """Build a client whose HTTP layer is the given mock handler."""
    return OllamaClient(transport=httpx.MockTransport(handler))


def chat_response(content: str) -> httpx.Response:
    """Shape of a non-streaming /api/chat reply from Ollama."""
    return httpx.Response(
        200, json={"message": {"role": "assistant", "content": content}, "done": True}
    )


def ndjson_stream(*tokens: str) -> str:
    """Shape of a streaming /api/chat reply: newline-delimited JSON, one per token."""
    lines = [json.dumps({"message": {"content": t}, "done": False}) for t in tokens]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# chat()
# --------------------------------------------------------------------------- #


async def test_chat_returns_plain_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        assert json.loads(request.content)["stream"] is False
        return chat_response("Hello from your laptop.")

    result = await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert result == "Hello from your laptop."


async def test_chat_defaults_to_scoring_temperature() -> None:
    """Scoring temperature is the safe default; creative callers opt in."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return chat_response("ok")

    await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert captured["options"]["temperature"] == get_settings().TEMPERATURE_SCORING


async def test_chat_uses_configured_model_by_default() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return chat_response("ok")

    await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert captured["model"] == get_settings().CHAT_MODEL


# --------------------------------------------------------------------------- #
# chat() with a Pydantic schema
# --------------------------------------------------------------------------- #


async def test_chat_with_schema_sends_format_and_validates() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return chat_response('{"score": 8, "comment": "Solid STAR structure."}')

    result = await make_client(handler).chat(
        [{"role": "user", "content": "score this"}], json_schema=Score
    )

    # The JSON Schema is handed to Ollama so sampling is constrained, not just checked.
    assert captured["format"] == Score.model_json_schema()
    assert isinstance(result, Score)
    assert result.score == 8


async def test_chat_repairs_invalid_json_on_second_attempt() -> None:
    """A 3B model sometimes drops a field. One repair round usually fixes it."""
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if len(calls) == 1:
            return chat_response('{"score": 8}')  # missing `comment`
        return chat_response('{"score": 8, "comment": "Repaired."}')

    result = await make_client(handler).chat(
        [{"role": "user", "content": "score this"}], json_schema=Score
    )

    assert isinstance(result, Score)
    assert result.comment == "Repaired."
    assert len(calls) == 2

    # The repair prompt must show the model its own bad output plus the error.
    repair_messages = calls[1]["messages"]
    assert repair_messages[-2] == {"role": "assistant", "content": '{"score": 8}'}
    assert "did not match the required JSON schema" in repair_messages[-1]["content"]
    assert "comment" in repair_messages[-1]["content"]


async def test_chat_raises_after_two_validation_failures() -> None:
    """We retry exactly once — looping would burn minutes of CPU inference."""
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return chat_response('{"nonsense": true}')

    with pytest.raises(GenerationError) as exc_info:
        await make_client(handler).chat(
            [{"role": "user", "content": "score this"}], json_schema=Score
        )

    assert len(calls) == 2
    assert "validation twice" in exc_info.value.message
    assert exc_info.value.hint  # the UI always gets something actionable


# --------------------------------------------------------------------------- #
# chat_stream()
# --------------------------------------------------------------------------- #


async def test_chat_stream_yields_tokens_in_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, text=ndjson_stream("Hello", " from", " Ollama"))

    tokens = [
        token
        async for token in make_client(handler).chat_stream([{"role": "user", "content": "hi"}])
    ]

    assert tokens == ["Hello", " from", " Ollama"]
    assert "".join(tokens) == "Hello from Ollama"


async def test_chat_stream_defaults_to_creative_temperature() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, text=ndjson_stream("hi"))

    async for _ in make_client(handler).chat_stream([{"role": "user", "content": "hi"}]):
        pass

    assert captured["options"]["temperature"] == get_settings().TEMPERATURE_CREATIVE


async def test_chat_stream_survives_a_malformed_line() -> None:
    """A partial line must not abort a generation that is otherwise fine."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(
            [
                json.dumps({"message": {"content": "good"}, "done": False}),
                "{not json at all",
                json.dumps({"message": {"content": " end"}, "done": True}),
            ]
        )
        return httpx.Response(200, text=body)

    tokens = [
        token
        async for token in make_client(handler).chat_stream([{"role": "user", "content": "hi"}])
    ]

    assert tokens == ["good", " end"]


async def test_chat_stream_reports_mid_stream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=json.dumps({"error": "out of memory"}))

    with pytest.raises(GenerationError) as exc_info:
        async for _ in make_client(handler).chat_stream([{"role": "user", "content": "hi"}]):
            pass

    assert "out of memory" in exc_info.value.message


# --------------------------------------------------------------------------- #
# embed()
# --------------------------------------------------------------------------- #


async def test_embed_returns_vector() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        assert json.loads(request.content)["model"] == get_settings().EMBED_MODEL
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    assert await make_client(handler).embed("some resume text") == [0.1, 0.2, 0.3]


async def test_embed_accepts_legacy_response_shape() -> None:
    """Older Ollama builds answered with {"embedding": [...]} (singular)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": [0.4, 0.5]})

    assert await make_client(handler).embed("text") == [0.4, 0.5]


async def test_embed_raises_when_no_vector_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with pytest.raises(GenerationError):
        await make_client(handler).embed("text")


# --------------------------------------------------------------------------- #
# Error translation
# --------------------------------------------------------------------------- #


async def test_connection_refused_becomes_ollama_down_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(OllamaDownError) as exc_info:
        await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert "ollama serve" in exc_info.value.hint


async def test_timeout_becomes_generation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    with pytest.raises(GenerationError) as exc_info:
        await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert "did not respond" in exc_info.value.message


async def test_http_404_becomes_model_missing_error() -> None:
    """Ollama answers 404 when the model was never pulled — the commonest failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'llama3.2:3b' not found"})

    with pytest.raises(ModelMissingError) as exc_info:
        await make_client(handler).chat([{"role": "user", "content": "hi"}])

    assert f"ollama pull {get_settings().CHAT_MODEL}" in exc_info.value.hint


async def test_http_500_becomes_generation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    with pytest.raises(GenerationError):
        await make_client(handler).chat([{"role": "user", "content": "hi"}])


async def test_stream_404_becomes_model_missing_error() -> None:
    """The streaming path needs its own status check — headers arrive first."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(ModelMissingError):
        async for _ in make_client(handler).chat_stream([{"role": "user", "content": "hi"}]):
            pass


# --------------------------------------------------------------------------- #
# list_models() and name handling
# --------------------------------------------------------------------------- #


async def test_list_models_returns_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200, json={"models": [{"name": "llama3.2:3b"}, {"name": "nomic-embed-text:latest"}]}
        )

    assert await make_client(handler).list_models() == ["llama3.2:3b", "nomic-embed-text:latest"]


async def test_ensure_model_available_raises_for_missing_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "phi3.5:latest"}]})

    with pytest.raises(ModelMissingError):
        await make_client(handler).ensure_model_available("llama3.2:3b")


def test_untagged_name_normalises_to_latest() -> None:
    assert normalise_model_name("nomic-embed-text") == "nomic-embed-text:latest"
    assert normalise_model_name("llama3.2:3b") == "llama3.2:3b"
    assert find_missing_models(["nomic-embed-text"], ["nomic-embed-text:latest"]) == []
