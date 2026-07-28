"""Tests for the Phase 4 hardening endpoints: setup, settings, stats, and the
global Ollama exception handler (all with a stubbed Ollama)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import runtime_config
from app.config import get_settings
from app.db import create_db_engine, get_session, init_db
from app.llm.client import OllamaDownError
from app.main import app
from app.routers import settings as settings_router
from app.routers import setup as setup_router

MODELS = ["llama3.2:3b", "llama3.2:1b", "nomic-embed-text:latest"]


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'sys.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Keep the runtime-settings file out of the real data dir.
    monkeypatch.setattr(runtime_config, "_path", lambda: tmp_path / "runtime.json")

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def stub_models(monkeypatch: pytest.MonkeyPatch, module, models: list[str]) -> None:
    async def _list(timeout: float | None = None) -> list[str]:
        return models

    monkeypatch.setattr(module, "list_models", _list)


def stub_ollama_down(monkeypatch: pytest.MonkeyPatch, module) -> None:
    async def _raise(timeout: float | None = None):
        raise OllamaDownError("Could not connect", hint="Run: ollama serve")

    monkeypatch.setattr(module, "list_models", _raise)


def sse_events(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in text.split("\n\n"):
        event, data = "message", ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data += line[len("data: ") :]
        if data:
            events.append((event, json.loads(data)))
    return events


# --- Setup ---------------------------------------------------------------- #


def test_setup_status_ready(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_models(monkeypatch, setup_router, MODELS)
    body = client.get("/api/setup/status").json()
    assert body["ollama"]["reachable"] is True
    assert body["models"]["missing"] == []
    assert body["ready"] is True
    assert "stt_available" in body["voice"]
    assert body["data_path"].endswith(".db")


def test_setup_status_ollama_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_ollama_down(monkeypatch, setup_router)
    body = client.get("/api/setup/status").json()
    assert body["ollama"]["reachable"] is False
    assert body["ready"] is False
    assert set(body["models"]["missing"]) == set(body["models"]["required"].values())


def test_pull_streams_progress(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class StubClient:
        def __init__(self, *a, **k) -> None:
            pass

        async def pull_stream(self, model: str):
            for update in (
                {"status": "pulling manifest"},
                {"status": "downloading", "total": 100, "completed": 50},
                {"status": "success"},
            ):
                yield update

    monkeypatch.setattr(setup_router, "OllamaClient", StubClient)

    response = client.post("/api/setup/pull", json={"model": "llama3.2:1b"})
    events = sse_events(response.text)
    progress = [d for e, d in events if e == "progress"]
    assert any(p["percent"] == 50.0 for p in progress)
    assert any(e == "done" for e, _ in events)


# --- Settings ------------------------------------------------------------- #


def test_get_settings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_models(monkeypatch, settings_router, MODELS)
    body = client.get("/api/settings").json()
    assert body["chat_model"] == get_settings().CHAT_MODEL
    assert body["installed_models"] == MODELS
    assert body["data_path"].endswith(".db")


def test_switch_model_persists(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_models(monkeypatch, settings_router, MODELS)
    resp = client.put("/api/settings/model", json={"model": "llama3.2:1b"})
    assert resp.status_code == 200
    assert resp.json()["chat_model"] == "llama3.2:1b"
    # Persisted for the next read.
    assert client.get("/api/settings").json()["chat_model"] == "llama3.2:1b"
    assert runtime_config.get_active_chat_model() == "llama3.2:1b"


def test_switch_to_uninstalled_model_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_models(monkeypatch, settings_router, MODELS)
    resp = client.put("/api/settings/model", json={"model": "mixtral:8x7b"})
    assert resp.status_code == 404
    assert "pull" in resp.json()["detail"]["hint"]


def test_ollama_down_hits_global_handler(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A router that lets an OllamaError escape returns friendly JSON, not a 500."""
    stub_ollama_down(monkeypatch, settings_router)
    resp = client.put("/api/settings/model", json={"model": "llama3.2:1b"})
    assert resp.status_code == 503
    assert "hint" in resp.json()["detail"]
    assert "ollama serve" in resp.json()["detail"]["hint"]


# --- Delete all data ------------------------------------------------------ #


def test_delete_data_requires_typed_confirmation(client: TestClient) -> None:
    resp = client.request("DELETE", "/api/settings/data", json={"confirm": "yes"})
    assert resp.status_code == 400
    assert "DELETE" in resp.json()["detail"]["hint"]


def test_delete_data_wipes_everything(client: TestClient) -> None:
    client.post("/api/outreach/contacts", json={"name": "Sam"})
    assert len(client.get("/api/outreach/contacts").json()) == 1

    resp = client.request("DELETE", "/api/settings/data", json={"confirm": "DELETE"})
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert client.get("/api/outreach/contacts").json() == []


# --- Stats ---------------------------------------------------------------- #


def test_stats_empty(client: TestClient) -> None:
    body = client.get("/api/stats").json()
    assert body["resume"] is None
    assert body["interviews"] == {"count": 0, "score_trend": [], "latest_average": None}
    assert body["roadmap"]["percent"] == 0
    assert body["outreach"]["reply_rate"] == 0


def test_stats_counts_contacts(client: TestClient) -> None:
    client.post("/api/outreach/contacts", json={"name": "Sam"})
    body = client.get("/api/stats").json()
    assert body["outreach"]["contacts"] == 1
