"""Tests for the Phase 3 career-roadmap feature (stubbed Ollama)."""

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
from app.services import indexing, roadmap_service

DIM = get_settings().EMBED_DIM

RESUME_TEXT = (
    "AARAV SHARMA\n\nEXPERIENCE\nWeb Development Intern, Nexus Softwares, May 2025. "
    "Fixed React bugs and wrote SQL.\n\nSKILLS\nPython, SQL, React, Flask, Git\n"
)

SKILL_GAP = {
    "skills": [
        {
            "skill": "Python",
            "required_level": 4,
            "current_level": 2,
            "priority": "high",
            "evidence": "wrote SQL and fixed React bugs",
        },
        {
            "skill": "Docker",
            "required_level": 3,
            "current_level": 1,
            "priority": "medium",
            "evidence": "not found",
        },
    ]
}

ROADMAP = {
    "phases": [
        {
            "name": "now",
            "actions": [
                {
                    "skill": "Python",
                    "action": "Complete an intermediate Python course",
                    "type": "course",
                    "why": "Core language depth for the role",
                },
                {
                    "skill": "Docker",
                    "action": "Containerize a small personal project",
                    "type": "project",
                    "why": "Hands-on containerization practice",
                },
            ],
        },
        {
            "name": "short",
            "actions": [
                {
                    "skill": "Python",
                    "action": "Build and deploy a REST API project",
                    "type": "project",
                    "why": "Apply Python to a realistic backend",
                }
            ],
        },
        {
            "name": "long",
            "actions": [
                {
                    "skill": "Docker",
                    "action": "Earn a container-orchestration certification",
                    "type": "cert",
                    "why": "Credential for production readiness",
                }
            ],
        },
    ]
}


def _chat_for(payload: dict) -> httpx.Response:
    """Return skill-gap or roadmap JSON depending on the constrained schema."""
    props = payload.get("format", {}).get("properties", {})
    body = SKILL_GAP if "skills" in props else ROADMAP
    return httpx.Response(200, json={"message": {"content": json.dumps(body)}})


def transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        return _chat_for(json.loads(request.content))

    return httpx.MockTransport(handler)


def stub_client() -> OllamaClient:
    return OllamaClient(transport=transport())


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'roadmap.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    real = indexing.index_document

    async def patched(session, source_type, source_id, text, *, client=None):
        return await real(session, source_type, source_id, text, client=stub_client())

    monkeypatch.setattr("app.routers.resumes.index_document", patched)
    monkeypatch.setattr(roadmap_service, "OllamaClient", stub_client)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def seed_resume(client: TestClient) -> int:
    return client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT}).json()["id"]


def sse_events(text: str) -> list[tuple[str, dict]]:
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


def generate(client: TestClient, payload: dict) -> dict:
    """POST the streaming endpoint and return the `done` event payload."""
    response = client.post("/api/roadmap", json=payload)
    assert response.status_code == 200, response.text
    done = [data for event, data in sse_events(response.text) if event == "done"]
    assert done, f"no done event: {response.text}"
    return done[0]


def test_generates_persists_and_computes_gap(client: TestClient) -> None:
    resume_id = seed_resume(client)

    done = generate(client, {"resume_id": resume_id, "target_role": "Backend Engineer"})
    roadmap = done["roadmap"]

    # Skill-gap table, with gap computed server-side (required - current).
    gaps = {g["skill"]: g for g in roadmap["skill_gap"]}
    assert gaps["Python"]["gap"] == 2
    assert gaps["Docker"]["gap"] == 2

    # Three horizon columns, always present and in order.
    assert [p["horizon"] for p in roadmap["phases"]] == ["now", "3_month", "12_month"]
    assert all(p["label"] for p in roadmap["phases"])

    now_actions = roadmap["phases"][0]["actions"]
    assert len(now_actions) == 2
    action = now_actions[0]
    assert action["type"] == "course"
    assert action["why"]  # rationale carried from plan_json
    assert action["done"] is False
    assert isinstance(action["item_id"], int)

    # Survives a fresh read (SOW: generated, saved, reopened).
    reopened = client.get(f"/api/roadmap/{done['plan_id']}")
    assert reopened.status_code == 200
    assert reopened.json()["target_role"] == "Backend Engineer"


def test_skill_gap_prompt_is_grounded_and_low_temperature(client: TestClient) -> None:
    resume_id = seed_resume(client)
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        payload = json.loads(request.content)
        captured.append(payload)
        return _chat_for(payload)

    monkeypatch_client = lambda: OllamaClient(transport=httpx.MockTransport(handler))  # noqa: E731
    roadmap_service.OllamaClient = monkeypatch_client

    generate(client, {"resume_id": resume_id, "target_role": "Data Engineer"})

    skill_gap_call = next(
        c for c in captured if "skills" in c.get("format", {}).get("properties", {})
    )
    prompt = skill_gap_call["messages"][0]["content"]
    assert "Data Engineer" in prompt
    assert "AARAV SHARMA" in prompt or "Python" in prompt  # resume context injected
    assert skill_gap_call["options"]["temperature"] == get_settings().TEMPERATURE_SCORING


def test_patch_toggles_done_and_updates_counts(client: TestClient) -> None:
    resume_id = seed_resume(client)
    done = generate(client, {"resume_id": resume_id, "target_role": "Backend Engineer"})
    plan_id = done["plan_id"]
    item_id = done["roadmap"]["phases"][0]["actions"][0]["item_id"]

    patched = client.patch(f"/api/roadmap/items/{item_id}", json={"done": True})
    assert patched.status_code == 200
    assert patched.json() == {"item_id": item_id, "done": True}

    # Reflected on reopen and in the listing counts.
    reopened = client.get(f"/api/roadmap/{plan_id}").json()
    assert reopened["phases"][0]["actions"][0]["done"] is True

    summary = next(r for r in client.get("/api/roadmap").json() if r["id"] == plan_id)
    assert summary["total_count"] == 4
    assert summary["done_count"] == 1


def test_regenerate_keeps_checked_progress(client: TestClient) -> None:
    resume_id = seed_resume(client)
    first = generate(client, {"resume_id": resume_id, "target_role": "Backend Engineer"})
    plan_id = first["plan_id"]
    item_id = first["roadmap"]["phases"][0]["actions"][0]["item_id"]
    client.patch(f"/api/roadmap/items/{item_id}", json={"done": True})

    again = generate(
        client,
        {"resume_id": resume_id, "target_role": "Backend Engineer", "regenerate_plan_id": plan_id},
    )

    assert again["plan_id"] == plan_id  # same plan, regenerated in place
    # The action whose text is unchanged keeps its tick.
    regenerated_action = again["roadmap"]["phases"][0]["actions"][0]
    assert regenerated_action["done"] is True

    # Still exactly one plan and one ticked action.
    plans = client.get("/api/roadmap").json()
    assert len(plans) == 1
    assert plans[0]["done_count"] == 1


def test_delete_roadmap(client: TestClient) -> None:
    resume_id = seed_resume(client)
    plan_id = generate(client, {"resume_id": resume_id, "target_role": "QA Engineer"})["plan_id"]

    assert client.delete(f"/api/roadmap/{plan_id}").status_code == 204
    assert client.get(f"/api/roadmap/{plan_id}").status_code == 404
    assert client.get("/api/roadmap").json() == []


def test_404_for_missing_resume(client: TestClient) -> None:
    response = client.post(
        "/api/roadmap", json={"resume_id": 999, "target_role": "Backend Engineer"}
    )
    assert response.status_code == 404
    assert "hint" in response.json()["detail"]
