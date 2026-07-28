"""Tests for the Phase 3a outreach drafter (stubbed Ollama)."""

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
from app.services import indexing, outreach_service

DIM = get_settings().EMBED_DIM

RESUME_TEXT = (
    "AARAV SHARMA\nSKILLS: Python, SQL, React, Flask, Git\nBuilt a REST API with FastAPI.\n"
)

DRAFT_OK = {
    "variants": [
        {
            "tone": "concise-formal",
            "subject": "Question about your FastAPI talk",
            "text": "Hi Priya, I saw your FastAPI talk and loved the caching section. "
            "I'm a fresher exploring backend roles — could I ask one question about your team?",
        },
        {
            "tone": "warm",
            "subject": "Loved your talk!",
            "text": "Hi Priya! Your FastAPI talk made async finally click for me. "
            "I'd love to hear how you got into backend work if you have a moment.",
        },
        {
            "tone": "direct",
            "subject": "Backend advice?",
            "text": "Hi Priya, your FastAPI talk was great. I'm targeting backend roles — "
            "any advice for a fresher breaking in?",
        },
    ]
}


def _chat_response(payload: dict) -> httpx.Response:
    if "variants" in payload.get("format", {}).get("properties", {}):
        return httpx.Response(200, json={"message": {"content": json.dumps(DRAFT_OK)}})
    # A shorten/repair call (no JSON schema) — return a short line.
    return httpx.Response(200, json={"message": {"content": "Short rewritten message."}})


def transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        return _chat_response(json.loads(request.content))

    return httpx.MockTransport(handler)


def stub_client() -> OllamaClient:
    return OllamaClient(transport=transport())


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'outreach.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    real = indexing.index_document

    async def patched(session, source_type, source_id, text, *, client=None):
        return await real(session, source_type, source_id, text, client=stub_client())

    monkeypatch.setattr("app.routers.resumes.index_document", patched)
    monkeypatch.setattr(outreach_service, "OllamaClient", stub_client)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def seed(client: TestClient) -> int:
    """Create a resume (for grounding) and a contact; return the contact id."""
    client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})
    return client.post(
        "/api/outreach/contacts",
        json={
            "name": "Priya Menon",
            "role": "Backend Lead",
            "company": "Nova",
            "notes": "Gave a FastAPI talk",
        },
    ).json()["id"]


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


def draft(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/outreach/draft", json=payload)
    assert response.status_code == 200, response.text
    done = [data for event, data in sse_events(response.text) if event == "done"]
    assert done, f"no done event: {response.text}"
    return done[0]


# --- Contact CRUD --------------------------------------------------------- #


def test_contact_crud(client: TestClient) -> None:
    created = client.post(
        "/api/outreach/contacts", json={"name": "Sam Rao", "company": "Acme"}
    ).json()
    cid = created["id"]
    assert created["name"] == "Sam Rao"

    listed = client.get("/api/outreach/contacts").json()
    assert any(c["id"] == cid for c in listed)

    updated = client.patch(f"/api/outreach/contacts/{cid}", json={"role": "Recruiter"}).json()
    assert updated["role"] == "Recruiter"
    assert updated["name"] == "Sam Rao"  # unchanged fields preserved

    assert client.delete(f"/api/outreach/contacts/{cid}").status_code == 204
    assert client.get(f"/api/outreach/contacts/{cid}").status_code == 404


def test_contact_name_required(client: TestClient) -> None:
    assert client.post("/api/outreach/contacts", json={"name": ""}).status_code == 422


# --- Draft generation ----------------------------------------------------- #


def test_generates_three_variants_and_persists(client: TestClient) -> None:
    contact_id = seed(client)

    done = draft(
        client,
        {
            "contact_id": contact_id,
            "purpose": "cold",
            "platform": "email",
            "hook": "your FastAPI talk",
        },
    )

    drafts = done["drafts"]
    assert len(drafts) == 3
    assert {d["tone"] for d in drafts} == {"concise-formal", "warm", "direct"}
    assert all(d["variant_no"] == i + 1 for i, d in enumerate(drafts))
    assert all(d["subject"] for d in drafts)  # email keeps subjects
    assert all(d["status"] == "draft" for d in drafts)

    # Persisted under the contact.
    contact = client.get(f"/api/outreach/contacts/{contact_id}").json()
    assert len(contact["drafts"]) == 3


def test_hook_is_required(client: TestClient) -> None:
    contact_id = seed(client)
    response = client.post(
        "/api/outreach/draft",
        json={"contact_id": contact_id, "purpose": "cold", "platform": "email", "hook": "   "},
    )
    assert response.status_code == 422
    assert "hook" in response.json()["detail"]["message"].lower()


def test_linkedin_note_length_enforced(client: TestClient) -> None:
    """A variant over 300 chars is shortened; nothing persists over the limit."""
    contact_id = seed(client)
    long_text = "I really enjoyed your FastAPI talk. " * 20  # ~720 chars, over 300

    over = {
        "variants": [
            {"tone": "concise-formal", "subject": None, "text": long_text},
            {"tone": "warm", "subject": None, "text": "Short and sweet, under the limit."},
            {"tone": "direct", "subject": None, "text": "Also short."},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * DIM]})
        payload = json.loads(request.content)
        if "variants" in payload.get("format", {}).get("properties", {}):
            return httpx.Response(200, json={"message": {"content": json.dumps(over)}})
        # shorten call returns a compliant rewrite
        return httpx.Response(
            200, json={"message": {"content": "Loved your FastAPI talk — quick question?"}}
        )

    outreach_service.OllamaClient = lambda: OllamaClient(transport=httpx.MockTransport(handler))

    done = draft(
        client,
        {
            "contact_id": contact_id,
            "purpose": "cold",
            "platform": "linkedin_note",
            "hook": "your FastAPI talk",
        },
    )

    for d in done["drafts"]:
        assert d["char_count"] <= 300
        assert d["char_limit"] == 300
        assert d["subject"] is None  # linkedin_note has no subject


def test_mark_sent_then_replied(client: TestClient) -> None:
    contact_id = seed(client)
    done = draft(
        client,
        {"contact_id": contact_id, "purpose": "referral", "platform": "email", "hook": "your talk"},
    )
    draft_id = done["drafts"][0]["id"]

    sent = client.patch(f"/api/outreach/drafts/{draft_id}", json={"status": "sent"}).json()
    assert sent["status"] == "sent"
    replied = client.patch(f"/api/outreach/drafts/{draft_id}", json={"status": "replied"}).json()
    assert replied["status"] == "replied"


def test_404_for_missing_contact(client: TestClient) -> None:
    response = client.post(
        "/api/outreach/draft",
        json={"contact_id": 999, "purpose": "cold", "platform": "email", "hook": "x"},
    )
    assert response.status_code == 404


# --- Unit: sentence-boundary truncation ----------------------------------- #


def test_truncate_at_sentence_prefers_boundary() -> None:
    text = "First sentence here. Second sentence that runs well past the hard limit boundary."
    out = outreach_service._truncate_at_sentence(text, 30)
    assert out == "First sentence here."
    assert len(out) <= 30


def test_truncate_falls_back_to_word_boundary() -> None:
    text = "supercalifragilistic expialidocious wordy phrase with no early sentence end"
    out = outreach_service._truncate_at_sentence(text, 25)
    assert len(out) <= 25
    assert not out.endswith("expialidocious")  # cut at a space, not mid-word
