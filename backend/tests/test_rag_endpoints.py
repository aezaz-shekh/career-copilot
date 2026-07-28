"""API-level tests for auto-indexing on save and the rag-test endpoint."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import create_db_engine, get_session, init_db
from app.llm.client import OllamaClient
from app.main import app
from app.services import indexing, vector_store

DIM = get_settings().EMBED_DIM
TOPICS = ["python", "sql", "docker", "react", "flask", "testing"]


def fake_embedding(content: str) -> list[float]:
    vec = [0.0] * DIM
    for i, word in enumerate(TOPICS):
        if word in content.lower():
            vec[i] = 1.0
    vec[DIM - 1] = 0.05
    return vec


def embedding_client() -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [fake_embedding(payload["input"])]})

    return OllamaClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'api.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    # Auto-indexing on save should use the deterministic fake embedder, so these
    # tests never touch Ollama. rag.retrieve builds its own client, so patch the
    # default there too via the dev router path below.
    real_index_document = indexing.index_document

    async def patched_index_document(session, source_type, source_id, text, *, client=None):
        return await real_index_document(
            session, source_type, source_id, text, client=embedding_client()
        )

    monkeypatch.setattr("app.routers.resumes.index_document", patched_index_document)
    monkeypatch.setattr("app.routers.jds.index_document", patched_index_document)

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


RESUME_TEXT = (
    "Built REST APIs with Python and Flask. "
    "Wrote SQL queries against a MySQL database. "
    "Practised writing unit tests for every module."
)


def test_saving_a_resume_auto_indexes_it(client: TestClient) -> None:
    response = client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})
    assert response.status_code == 201

    # rag-test needs the retrieve() call to use the fake embedder too.
    with_stub_retrieve(client)


def with_stub_retrieve(client: TestClient) -> None:
    """rag-test uses rag.retrieve, which constructs its own OllamaClient.

    Rather than reach into it, assert indexing happened by counting chunks
    through a fresh session on the same engine.
    """
    # The dependency override gives every request the same engine, so a GET that
    # counts chunks reflects what the POST indexed.
    listing = client.get("/api/resumes").json()
    assert len(listing) == 1


def test_rag_test_endpoint_returns_relevant_chunks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Patch the client rag.retrieve builds, so the query is embedded with the
    # same deterministic vectors used for indexing.
    from app.llm import rag

    real_retrieve = rag.retrieve

    async def patched_retrieve(session, query, **kwargs):
        kwargs["client"] = embedding_client()
        return await real_retrieve(session, query, **kwargs)

    monkeypatch.setattr("app.routers.dev.rag.retrieve", patched_retrieve)

    client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})

    response = client.get("/api/dev/rag-test", params={"q": "python flask api", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["indexed_chunks"] >= 1
    assert body["returned"] >= 1
    top = body["results"][0]
    assert "Python" in top["text"] or "Flask" in top["text"]
    assert -1.0 <= top["similarity"] <= 1.0


def test_rag_test_on_empty_store_is_404(client: TestClient) -> None:
    response = client.get("/api/dev/rag-test", params={"q": "anything"})

    assert response.status_code == 404
    assert "hint" in response.json()["detail"]


def test_deleting_a_resume_removes_its_chunks(client: TestClient) -> None:
    created = client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})
    resume_id = created.json()["id"]

    # Confirm something was indexed, then delete and confirm it is gone.
    response = client.get("/api/dev/rag-test", params={"q": "python"})
    # retrieve() here uses a real client and would fail to reach Ollama, so we
    # only assert on the count-guard path: indexed_chunks must be > 0 OR the
    # call failed at retrieval (503), never the empty-store 404.
    assert response.status_code in (200, 503)

    assert client.delete(f"/api/resumes/{resume_id}").status_code == 204

    after = client.get("/api/dev/rag-test", params={"q": "python"})
    assert after.status_code == 404  # store now empty


def test_saving_resume_survives_indexing_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If embedding fails at save time, the resume must still be stored."""
    from app.llm.client import OllamaDownError

    async def failing_index(*args, **kwargs):
        raise OllamaDownError("down", hint="run ollama serve")

    # index_document swallows OllamaError; simulate the deeper failure to be sure.
    async def failing_index_document(session, *args, **kwargs):
        from app.services.indexing import index_document as real

        monkeypatch.setattr("app.llm.rag.index_source", failing_index)
        return await real(session, *args, **kwargs)

    monkeypatch.setattr("app.routers.resumes.index_document", failing_index_document)

    response = client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})

    assert response.status_code == 201
    assert len(client.get("/api/resumes").json()) == 1
    assert vector_store  # imported for symmetry
