"""Async client wrapper around the local Ollama REST API.

This is the single choke point for every call to the LLM (SOW Section 6.1,
Layer 3: "an LLM client wrapper around Ollama's REST API with retry, timeout and
streaming support"). Nothing else in the codebase may call Ollama directly.

Three responsibilities:

1. **Transport** — timeouts sized for CPU-only inference, and translation of
   every httpx failure into a typed exception carrying a plain-language `hint`,
   so the UI never shows a stack trace (SOW Section 7, Reliability).
2. **Structured output** — when a Pydantic schema is supplied, Ollama's `format`
   parameter constrains generation to that JSON shape; the reply is then parsed
   and validated, with one automatic repair attempt on failure (SOW Section 11:
   "structured JSON output with schema validation").
3. **Streaming** — token-by-token generation so the UI feels live while a 3B
   model works through a prompt on CPU.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# A chat message in Ollama's format: {"role": "system"|"user"|"assistant", "content": "..."}
Message = dict[str, str]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class OllamaError(RuntimeError):
    """Base class for every LLM failure.

    Carries two strings deliberately: `message` is technical and goes to the log,
    `hint` is what the user reads and tells them exactly what to do next.
    """

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class OllamaDownError(OllamaError):
    """Ollama is not running, not listening, or refused the connection."""


class ModelMissingError(OllamaError):
    """Ollama is running but the requested model has not been pulled."""


class GenerationError(OllamaError):
    """The model was reached but generation failed, timed out, or produced
    output that could not be validated against the requested schema."""


# --------------------------------------------------------------------------- #
# Model-name helpers
# --------------------------------------------------------------------------- #


def normalise_model_name(name: str) -> str:
    """Return a model name with an explicit tag.

    Ollama always reports pulled models with a tag attached, so a model pulled as
    ``nomic-embed-text`` is listed as ``nomic-embed-text:latest``. Without this
    normalisation, availability checks would wrongly report it as missing.
    """
    return name if ":" in name else f"{name}:latest"


def find_missing_models(required: Sequence[str], installed: Sequence[str]) -> list[str]:
    """Return the required models that are absent from `installed`."""
    installed_tags = {normalise_model_name(name) for name in installed}
    return [name for name in required if normalise_model_name(name) not in installed_tags]


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class OllamaClient:
    """Async client for a locally running Ollama server.

    Args:
        base_url: Ollama root URL. Defaults to the configured OLLAMA_URL.
        model: Default chat model. Defaults to the configured CHAT_MODEL.
        timeout: Per-request timeout in seconds. Defaults to OLLAMA_TIMEOUT.
        transport: Optional httpx transport — the injection point that lets the
            test suite run the whole client against a mocked HTTP layer with no
            Ollama installed.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from app import runtime_config

        settings = get_settings()
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        # The active chat model can be changed at runtime via the Settings page,
        # so read the override rather than the frozen default.
        self.model = model or runtime_config.get_active_chat_model()
        self.embed_model = settings.EMBED_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT if timeout is None else timeout
        self._transport = transport

    # -- internals ---------------------------------------------------------- #

    def _http(self, timeout: float | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout if timeout is None else timeout,
            transport=self._transport,
        )

    def _transport_error(self, exc: Exception) -> OllamaError:
        """Translate a raw httpx exception into a typed, user-facing error."""
        if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout):
            return OllamaDownError(
                f"Could not connect to Ollama at {self.base_url}",
                hint="Ollama is not running. Open a terminal and run: ollama serve",
            )
        if isinstance(exc, httpx.TimeoutException):
            return GenerationError(
                f"Ollama did not respond within {self.timeout:.0f}s",
                hint=(
                    "The model is still loading into RAM, or the prompt is very long. "
                    "Try again — the first request after startup is always the slowest."
                ),
            )
        return GenerationError(
            f"Unexpected transport error talking to Ollama: {exc}",
            hint="Check that Ollama is running, then retry.",
        )

    def _raise_for_status(self, status_code: int, body: str, model: str) -> None:
        """Convert a non-2xx Ollama response into a typed exception.

        Ollama answers 404 for an un-pulled model, which is the single most
        common failure for a new user — it gets its own exception type so the UI
        can show the exact `ollama pull` command.
        """
        if status_code == 404:
            raise ModelMissingError(
                f"Model '{model}' is not available in local Ollama",
                hint=f"Download it once with: ollama pull {model}",
            )
        if status_code >= 400:
            raise GenerationError(
                f"Ollama returned HTTP {status_code}: {body[:300]}",
                hint="Restart Ollama and try again.",
            )

    def _chat_payload(
        self,
        messages: Sequence[Message],
        model: str,
        temperature: float,
        *,
        stream: bool,
        json_schema: type[BaseModel] | None = None,
        num_predict: int | None = None,
        keep_alive: str | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": temperature}
        if num_predict is not None:
            # Hard cap on generated tokens, so replies stay snappy.
            options["num_predict"] = num_predict
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "stream": stream,
            "options": options,
        }
        if keep_alive is not None:
            # Keep the model resident in RAM so the next request skips the
            # cold-start reload that otherwise looks like a hang.
            payload["keep_alive"] = keep_alive
        if json_schema is not None:
            # Ollama constrains sampling to this JSON Schema, which makes
            # malformed output rare rather than something we merely detect.
            payload["format"] = json_schema.model_json_schema()
        return payload

    async def _chat_once(self, payload: dict[str, Any], timeout: float | None = None) -> str:
        """POST /api/chat without streaming and return the assistant's text."""
        model = payload["model"]
        try:
            async with self._http(timeout) as http:
                response = await http.post("/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

        self._raise_for_status(response.status_code, response.text, model)

        try:
            data = response.json()
        except ValueError as exc:
            raise GenerationError(
                "Ollama returned a response that was not valid JSON",
                hint="Restart Ollama and try again.",
            ) from exc

        if data.get("error"):
            raise GenerationError(
                f"Ollama reported an error: {data['error']}",
                hint="Check the Ollama terminal window for details.",
            )

        return data.get("message", {}).get("content", "")

    # -- public API --------------------------------------------------------- #

    async def list_models(self, timeout: float | None = None) -> list[str]:
        """Return the names of every model currently pulled into local Ollama."""
        settings = get_settings()
        try:
            async with self._http(timeout or settings.HEALTH_TIMEOUT) as http:
                response = await http.get("/api/tags")
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

        self._raise_for_status(response.status_code, response.text, self.model)
        return [model["name"] for model in response.json().get("models", [])]

    async def ensure_model_available(self, model: str | None = None) -> None:
        """Raise ModelMissingError if `model` has not been pulled locally."""
        model = model or self.model
        if find_missing_models([model], await self.list_models()):
            raise ModelMissingError(
                f"Model '{model}' is not available in local Ollama",
                hint=f"Download it once with: ollama pull {model}",
            )

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        json_schema: type[SchemaT] | None = None,
        timeout: float | None = None,
    ) -> str | SchemaT:
        """Generate a complete (non-streamed) reply.

        Args:
            messages: Conversation in Ollama chat format.
            model: Override the default chat model.
            temperature: Sampling temperature. Defaults to TEMPERATURE_SCORING,
                the conservative choice — creative callers opt in explicitly.
            json_schema: A Pydantic model class. When supplied, generation is
                constrained to its JSON Schema and the reply is validated
                against it.
            timeout: Override the default timeout. Long structured outputs need
                it — a full resume takes minutes at 3 tokens/second.

        Returns:
            The reply text, or a validated instance of `json_schema`.

        Raises:
            OllamaDownError, ModelMissingError, GenerationError.
        """
        settings = get_settings()
        model = model or self.model
        temperature = settings.TEMPERATURE_SCORING if temperature is None else temperature
        payload = self._chat_payload(
            messages, model, temperature, stream=False, json_schema=json_schema
        )

        raw = await self._chat_once(payload, timeout)

        if json_schema is None:
            return raw

        try:
            return json_schema.model_validate_json(raw)
        except (ValidationError, ValueError) as first_error:
            # Capture the text now: Python unbinds `first_error` when the except
            # block ends, and we need the message in the repair prompt below.
            first_error_text = str(first_error)
            logger.warning(
                "Model output failed %s validation, attempting one repair", json_schema.__name__
            )

        # One repair attempt: show the model its own output and the validator's
        # complaint. Small models usually fix themselves given the exact error.
        # We retry exactly once — a second failure means the prompt is wrong, and
        # looping would only burn minutes of CPU inference.
        repair_payload = self._chat_payload(
            [
                *messages,
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        "Your previous reply did not match the required JSON schema.\n"
                        f"Validation error:\n{first_error_text}\n\n"
                        "Reply again with ONLY valid JSON matching the schema. "
                        "No explanation, no markdown fences."
                    ),
                },
            ],
            model,
            temperature,
            stream=False,
            json_schema=json_schema,
        )
        repaired = await self._chat_once(repair_payload, timeout)

        try:
            return json_schema.model_validate_json(repaired)
        except (ValidationError, ValueError) as second_error:
            raise GenerationError(
                f"Model output failed {json_schema.__name__} validation twice: {second_error}",
                hint=(
                    "The local model is struggling with this request. Try again, "
                    "or shorten the input text."
                ),
            ) from second_error

    async def chat_stream(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        num_predict: int | None = None,
        keep_alive: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield reply tokens as they are generated.

        Used wherever the user is waiting on generation, so the UI can render
        text immediately instead of freezing (SOW Section 7, Performance).
        """
        settings = get_settings()
        model = model or self.model
        temperature = settings.TEMPERATURE_CREATIVE if temperature is None else temperature
        payload = self._chat_payload(
            messages,
            model,
            temperature,
            stream=True,
            num_predict=num_predict,
            keep_alive=keep_alive,
        )

        try:
            async with (
                self._http() as http,
                http.stream("POST", "/api/chat", json=payload) as response,
            ):
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    self._raise_for_status(response.status_code, body, model)

                # Ollama streams newline-delimited JSON, one object per token.
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Skipping unparseable stream line: %r", line[:120])
                        continue

                    if chunk.get("error"):
                        raise GenerationError(
                            f"Ollama reported an error mid-stream: {chunk['error']}",
                            hint="Check the Ollama terminal window for details.",
                        )

                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

    async def pull_stream(self, model: str) -> AsyncIterator[dict]:
        """Stream Ollama's download progress while it pulls `model`.

        Yields the raw progress objects from /api/pull — a `status` string plus,
        on layer-download lines, `total` and `completed` byte counts. Used by the
        first-run setup wizard's progress bar. A pull can take minutes, so the
        read timeout is generous; progress lines arrive far more often than that.
        """
        payload = {"model": model, "stream": True}
        try:
            async with (
                self._http(timeout=3600.0) as http,
                http.stream("POST", "/api/pull", json=payload) as response,
            ):
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    self._raise_for_status(response.status_code, body, model)

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Skipping unparseable pull line: %r", line[:120])
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        """Return the embedding vector for `text` (used by the RAG pipeline)."""
        model = model or self.embed_model
        try:
            async with self._http() as http:
                response = await http.post("/api/embed", json={"model": model, "input": text})
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

        self._raise_for_status(response.status_code, response.text, model)
        data = response.json()

        # /api/embed returns {"embeddings": [[...]]}; the older /api/embeddings
        # route returned {"embedding": [...]}. Accept either.
        if isinstance(data.get("embeddings"), list) and data["embeddings"]:
            return data["embeddings"][0]
        if isinstance(data.get("embedding"), list):
            return data["embedding"]

        raise GenerationError(
            f"Embedding response from '{model}' contained no vector",
            hint=f"Confirm the model is an embedding model: ollama pull {model}",
        )


# --------------------------------------------------------------------------- #
# Module-level convenience
# --------------------------------------------------------------------------- #


async def list_models(timeout: float | None = None) -> list[str]:
    """Convenience wrapper for callers that need nothing but the model list."""
    return await OllamaClient().list_models(timeout=timeout)
