"""Tests for the Phase 2 question-bank generator."""

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
from app.services import indexing, interview_service

DIM = get_settings().EMBED_DIM

RESUME_TEXT = (
    "AARAV SHARMA\n\nEXPERIENCE\nWeb Development Intern, Nexus Softwares, May 2025. "
    "Fixed React bugs and wrote SQL.\n\nSKILLS\nPython, SQL, React, Flask, Git\n"
)
JD_TEXT = (
    "Junior Python Developer. Build REST APIs with FastAPI. Required: Python, SQL, "
    "Git, pytest. Nice to have: Docker, CI/CD."
)

QUESTIONS = {
    "questions": [
        {
            "question": "Tell me about a time you fixed a difficult bug.",
            "type": "behavioral",
            "looks_for": "Problem-solving and persistence",
            "difficulty": 2,
        },
        {
            "question": "Describe working in a team using Git.",
            "type": "behavioral",
            "looks_for": "Collaboration",
            "difficulty": 1,
        },
        {
            "question": "How would you design a REST endpoint in FastAPI?",
            "type": "technical",
            "looks_for": "API design knowledge",
            "difficulty": 3,
        },
        {
            "question": "Explain how you would write a unit test with pytest.",
            "type": "technical",
            "looks_for": "Testing fundamentals",
            "difficulty": 2,
        },
    ]
}


def transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            payload = json.loads(request.content)
            vec = [0.0] * DIM
            for i, kw in enumerate(["python", "sql", "react", "flask", "docker", "fastapi"]):
                if kw in payload["input"].lower():
                    vec[i] = 1.0
            vec[DIM - 1] = 0.05
            return httpx.Response(200, json={"embeddings": [vec]})
        return httpx.Response(200, json={"message": {"content": json.dumps(QUESTIONS)}})

    return httpx.MockTransport(handler)


def stub_client() -> OllamaClient:
    return OllamaClient(transport=transport())


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'iv.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    real = indexing.index_document

    async def patched(session, source_type, source_id, text, *, client=None):
        return await real(session, source_type, source_id, text, client=stub_client())

    monkeypatch.setattr("app.routers.resumes.index_document", patched)
    monkeypatch.setattr("app.routers.jds.index_document", patched)
    monkeypatch.setattr(interview_service, "OllamaClient", stub_client)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def seed(client: TestClient) -> tuple[int, int]:
    r = client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})
    j = client.post("/api/jds", json={"title": "Junior Python Developer", "raw_text": JD_TEXT})
    return r.json()["id"], j.json()["id"]


def sse_events(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE response body into a list of (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    for frame in text.split("\n\n"):
        event = "message"
        data = ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data += line[len("data: ") :]
        if data:
            events.append((event, json.loads(data)))
    return events


def generate_bank(client: TestClient, payload: dict) -> dict:
    """POST the streaming endpoint and return the `done` event's payload."""
    response = client.post("/api/interviews/questions", json=payload)
    assert response.status_code == 200
    events = sse_events(response.text)
    done = [data for event, data in events if event == "done"]
    assert done, f"no done event in stream: {events}"
    return done[0]


def test_generates_a_question_bank(client: TestClient) -> None:
    resume_id, jd_id = seed(client)

    body = generate_bank(client, {"resume_id": resume_id, "jd_id": jd_id})

    assert len(body["questions"]) == 4
    assert body["behavioral_count"] == 2
    assert body["technical_count"] == 2
    assert body["elapsed_ms"] >= 0

    q = body["questions"][0]
    assert set(q) == {"question", "type", "looks_for", "difficulty"}
    assert q["type"] in {"behavioral", "technical"}
    assert 1 <= q["difficulty"] <= 3


def test_request_carries_rag_context_and_counts(client: TestClient) -> None:
    """The prompt must contain retrieved resume/JD text and the requested counts."""
    resume_id, jd_id = seed(client)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            vec = [0.1] * DIM
            return httpx.Response(200, json={"embeddings": [vec]})
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(QUESTIONS)}})

    interview_service.OllamaClient = lambda: OllamaClient(transport=httpx.MockTransport(handler))

    generate_bank(
        client,
        {"resume_id": resume_id, "jd_id": jd_id, "n_behavioral": 6, "n_technical": 6},
    )

    prompt = captured["messages"][0]["content"]
    assert "6 behavioral" in prompt and "6 technical" in prompt
    assert "AARAV SHARMA" in prompt or "Python" in prompt  # resume context injected
    assert captured["options"]["temperature"] == get_settings().TEMPERATURE_CREATIVE


def test_difficulty_out_of_range_is_repaired_or_rejected(client: TestClient) -> None:
    """A difficulty of 5 violates the schema; the client repairs, then validates."""
    resume_id, jd_id = seed(client)
    calls: list[int] = []

    bad = {"questions": [{"question": "Q", "type": "technical", "looks_for": "x", "difficulty": 5}]}
    good = {
        "questions": [{"question": "Q", "type": "technical", "looks_for": "x", "difficulty": 3}]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        calls.append(1)
        payload = bad if len(calls) == 1 else good
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    interview_service.OllamaClient = lambda: OllamaClient(transport=httpx.MockTransport(handler))

    body = generate_bank(client, {"resume_id": resume_id, "jd_id": jd_id})

    assert body["questions"][0]["difficulty"] == 3
    assert len(calls) == 2  # one repair round happened


def test_counts_are_trimmed_to_the_request(client: TestClient) -> None:
    """The model over-generates; the service trims to the requested counts."""
    resume_id, jd_id = seed(client)

    many = {
        "questions": (
            [
                {"question": f"B{i}", "type": "behavioral", "looks_for": "x", "difficulty": 1}
                for i in range(9)
            ]
            + [
                {"question": f"T{i}", "type": "technical", "looks_for": "x", "difficulty": 2}
                for i in range(9)
            ]
        )
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        return httpx.Response(200, json={"message": {"content": json.dumps(many)}})

    interview_service.OllamaClient = lambda: OllamaClient(transport=httpx.MockTransport(handler))

    body = generate_bank(
        client,
        {"resume_id": resume_id, "jd_id": jd_id, "n_behavioral": 6, "n_technical": 6},
    )

    assert body["behavioral_count"] == 6
    assert body["technical_count"] == 6
    assert len(body["questions"]) == 12


def test_404_for_missing_resume(client: TestClient) -> None:
    _, jd_id = seed(client)
    response = client.post("/api/interviews/questions", json={"resume_id": 999, "jd_id": jd_id})
    assert response.status_code == 404
    assert "hint" in response.json()["detail"]


def test_404_for_missing_jd(client: TestClient) -> None:
    resume_id, _ = seed(client)
    response = client.post("/api/interviews/questions", json={"resume_id": resume_id, "jd_id": 999})
    assert response.status_code == 404
