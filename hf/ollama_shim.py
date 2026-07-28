"""Ollama-compatible shim backed by Groq (chat) and fastembed (embeddings).

Why this exists
---------------
The app talks to Ollama over `OLLAMA_URL` and nothing else. On free CPU hosting
a local 3B model needs 1-3 minutes per answer, which is unusable for a visitor
who is just trying the app. This process speaks Ollama's REST API but forwards
generation to Groq, so replies arrive in seconds.

Because it reimplements the same contract, **no application code changes**:
`OllamaClient` still posts to /api/chat, /api/tags and /api/embed exactly as it
does against real Ollama on a laptop.

Embeddings stay local. They are cheap on CPU (a few milliseconds) and keeping
them here means the RAG pipeline works without a second paid provider.
BAAI/bge-base-en-v1.5 emits 768 floats, matching the app's EMBED_DIM, so the
sqlite-vec table declaration needs no change.

Endpoints implemented (the only ones app/llm/client.py calls):
    GET  /api/tags    -> model list, so the health check reports "ok"
    POST /api/chat    -> non-streaming and streaming generation
    POST /api/embed   -> embedding vector
    POST /api/pull    -> no-op progress stream (setup wizard)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Every Ollama chat model name maps onto one Groq model. The app asks for
# llama3.2:3b (quality) and llama3.2:1b (speed); on Groq both are fast enough
# that a single model keeps the deployment simple.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# Advertised to /api/tags so health checks and the Setup tab see nothing missing.
ADVERTISED_MODELS = [
    os.environ.get("CHAT_MODEL", "llama3.2:3b"),
    os.environ.get("QUESTION_MODEL", "llama3.2:1b"),
    os.environ.get("EMBED_MODEL", "nomic-embed-text") + ":latest",
]

EMBED_MODEL_NAME = os.environ.get("HF_EMBED_MODEL", "BAAI/bge-base-en-v1.5")

app = FastAPI(title="Ollama shim (Groq-backed)")

_embedder: Any = None


def get_embedder() -> Any:
    """Load the ONNX embedding model once, on first use."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=EMBED_MODEL_NAME)
    return _embedder


def _to_groq_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Translate an Ollama /api/chat body into a Groq chat-completions body."""
    options = body.get("options") or {}
    payload: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": body.get("messages", []),
        "temperature": options.get("temperature", 0.7),
        "stream": bool(body.get("stream")),
    }

    # Ollama caps generated tokens with options.num_predict.
    if options.get("num_predict") is not None:
        payload["max_tokens"] = options["num_predict"]

    # Ollama constrains sampling to a JSON Schema via "format". Groq offers
    # json_object mode rather than full schema enforcement, so ask for JSON and
    # put the schema in the system prompt — the callers already validate and
    # repair the result, so a near-miss degrades instead of breaking.
    if body.get("format"):
        payload["response_format"] = {"type": "json_object"}
        schema = json.dumps(body["format"])
        messages = list(payload["messages"])
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "Reply with a single JSON object and nothing else. "
                    f"It must conform to this JSON Schema: {schema}"
                ),
            },
        )
        payload["messages"] = messages

    return payload


@app.get("/api/tags")
async def tags() -> dict[str, Any]:
    """Mimic Ollama's model listing so find_missing_models() finds nothing missing."""
    return {"models": [{"name": name} for name in ADVERTISED_MODELS]}


@app.post("/api/pull")
async def pull(request: Request) -> StreamingResponse:
    """The setup wizard streams a pull; nothing to download here."""

    async def gen():
        yield json.dumps({"status": "using hosted inference - nothing to download"}) + "\n"
        yield json.dumps({"status": "success"}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    payload = _to_groq_payload(body)
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    if not GROQ_API_KEY:
        return JSONResponse({"error": "GROQ_API_KEY is not set on this Space"}, status_code=500)

    # ---- streaming: translate SSE deltas into Ollama's newline-delimited JSON
    if payload["stream"]:

        async def gen():
            try:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    async with http.stream("POST", GROQ_URL, json=payload, headers=headers) as r:
                        if r.status_code >= 400:
                            detail = (await r.aread()).decode("utf-8", "replace")
                            yield json.dumps({"error": detail[:500]}) + "\n"
                            return
                        async for line in r.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            delta = chunk["choices"][0].get("delta", {}).get("content")
                            if delta:
                                yield json.dumps({"message": {"content": delta}, "done": False}) + "\n"
            except httpx.HTTPError as exc:
                yield json.dumps({"error": f"upstream transport error: {exc}"}) + "\n"
                return
            yield json.dumps({"message": {"content": ""}, "done": True}) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # ---- non-streaming
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            r = await http.post(GROQ_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        return JSONResponse({"error": f"upstream transport error: {exc}"}, status_code=502)

    if r.status_code >= 400:
        return JSONResponse({"error": r.text[:500]}, status_code=r.status_code)

    content = r.json()["choices"][0]["message"]["content"]
    return {"message": {"role": "assistant", "content": content}, "done": True}


@app.post("/api/embed")
async def embed(request: Request):
    body = await request.json()
    text = body.get("input") or ""
    if isinstance(text, list):
        text = text[0] if text else ""

    vector = list(next(iter(get_embedder().embed([text]))))
    return {"embeddings": [[float(x) for x in vector]]}


@app.get("/")
async def root() -> dict[str, str]:
    return {"shim": "ollama-compatible", "upstream": GROQ_MODEL}
