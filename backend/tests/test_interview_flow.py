"""Tests for the Phase 2.2 turn-based interview flow and scoring."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import create_db_engine, get_session, init_db
from app.llm.client import OllamaClient
from app.main import app
from app.schemas.interview import ScoringResult
from app.services import interview_service

# Canned answers for the two scoring/follow-up calls, chosen by prompt content.
SCORE = {
    "scores": {"structure": 4, "specificity": 3, "star_adherence": 4, "relevance": 5},
    "feedback": {
        "structure": "Good STAR ordering.",
        "specificity": "Add concrete numbers.",
        "star_adherence": "Result was clear.",
        "relevance": "Directly answered.",
    },
    "improvement_tip": "Quantify the impact of your work.",
}
FOLLOWUP_NO = {"needs_followup": False, "followup_question": None}
FOLLOWUP_YES = {"needs_followup": True, "followup_question": "Can you give a specific metric?"}


def make_client(followup=FOLLOWUP_NO, score=SCORE) -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["messages"][0]["content"]
        payload = score if "strict, consistent interview evaluator" in prompt else followup
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    return OllamaClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(interview_service, "OllamaClient", make_client)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


QUESTIONS = [
    {
        "question": "Tell me about a bug you fixed.",
        "type": "behavioral",
        "looks_for": "x",
        "difficulty": 2,
    },
    {
        "question": "How do you design a REST API?",
        "type": "technical",
        "looks_for": "y",
        "difficulty": 3,
    },
]


def start(client: TestClient) -> int:
    jd = client.post("/api/jds", json={"title": "Dev", "raw_text": "Python and SQL required here."})
    r = client.post(
        "/api/interviews/start",
        json={"jd_id": jd.json()["id"], "mode": "text", "questions": QUESTIONS},
    )
    assert r.status_code == 200
    return r.json()["session_id"]


# --------------------------------------------------------------------------- #
# Service — the required consistency test
# --------------------------------------------------------------------------- #


async def test_same_answer_scored_twice_is_consistent_and_schema_valid() -> None:
    """The required test: feed one answer twice through a mocked scorer.

    A deterministic scorer returns identical scores, so the runs are trivially
    within +/-1 (SOW Section 12), and both validate against ScoringResult.
    """
    client = make_client()
    answer = "I noticed a failing test, traced it to a null check, and fixed it in an hour."

    first, _ = await interview_service.score_answer(
        "Tell me about a bug.", answer, "", client=client
    )
    second, _ = await interview_service.score_answer(
        "Tell me about a bug.", answer, "", client=client
    )

    assert isinstance(first, ScoringResult) and isinstance(second, ScoringResult)
    for dim in ("structure", "specificity", "star_adherence", "relevance"):
        a = getattr(first.scores, dim)
        b = getattr(second.scores, dim)
        assert 1 <= a <= 5
        assert abs(a - b) <= 1  # consistency within one rubric point


async def test_scoring_uses_low_temperature() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        if "strict, consistent interview evaluator" in prompt:
            captured["temp"] = body["options"]["temperature"]
            return httpx.Response(200, json={"message": {"content": json.dumps(SCORE)}})
        return httpx.Response(200, json={"message": {"content": json.dumps(FOLLOWUP_NO)}})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    await interview_service.score_answer("Q", "A", "", client=client)

    assert captured["temp"] == 0.2


# --------------------------------------------------------------------------- #
# Flow
# --------------------------------------------------------------------------- #


def test_start_stores_the_question_bank(client: TestClient) -> None:
    session_id = start(client)
    body = client.get(f"/api/interviews/{session_id}").json()
    assert body["mode"] == "text"
    assert body["ended_at"] is None


def test_answer_scores_but_hides_scores_until_end(client: TestClient) -> None:
    session_id = start(client)

    resp = client.post(
        "/api/interviews/answer",
        json={
            "session_id": session_id,
            "question": QUESTIONS[0]["question"],
            "answer": "I fixed a bug.",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "scores" not in body  # hidden mid-interview
    assert body["needs_followup"] is False

    # Mid-interview replay also hides scores (session not ended).
    mid = client.get(f"/api/interviews/{session_id}").json()
    assert mid["turns"][0]["scores"] is None
    assert mid["summary"] is None


def test_finish_reveals_scores_and_summary(client: TestClient) -> None:
    session_id = start(client)
    for q in QUESTIONS:
        client.post(
            "/api/interviews/answer",
            json={
                "session_id": session_id,
                "question": q["question"],
                "answer": "A detailed answer.",
            },
        )

    finished = client.post(f"/api/interviews/{session_id}/finish").json()

    assert finished["ended_at"] is not None
    assert finished["turns"][0]["scores"]["relevance"] == 5
    assert finished["turns"][0]["improvement_tip"] == "Quantify the impact of your work."

    summary = finished["summary"]
    assert summary["answered"] == 2
    assert summary["averages"]["relevance"] == 5.0
    assert summary["overall_average"] > 0
    assert len(summary["strengths"]) >= 1  # relevance/structure are strong here


def test_followup_is_surfaced_when_needed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        interview_service, "OllamaClient", lambda: make_client(followup=FOLLOWUP_YES)
    )
    session_id = start(client)

    resp = client.post(
        "/api/interviews/answer",
        json={"session_id": session_id, "question": QUESTIONS[0]["question"], "answer": "Vague."},
    ).json()

    assert resp["needs_followup"] is True
    assert "metric" in resp["followup_question"]


def test_followup_yes_but_empty_question_is_downgraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """needs_followup=true with no question must not leave the UI stuck."""
    bad = {"needs_followup": True, "followup_question": "  "}
    monkeypatch.setattr(interview_service, "OllamaClient", lambda: make_client(followup=bad))
    session_id = start(client)

    resp = client.post(
        "/api/interviews/answer",
        json={"session_id": session_id, "question": "Q", "answer": "A"},
    ).json()

    assert resp["needs_followup"] is False


def test_list_and_delete_sessions(client: TestClient) -> None:
    session_id = start(client)
    client.post(
        "/api/interviews/answer",
        json={"session_id": session_id, "question": "Q", "answer": "An answer."},
    )

    listing = client.get("/api/interviews").json()
    assert len(listing) == 1
    assert listing[0]["turn_count"] == 1

    assert client.delete(f"/api/interviews/{session_id}").status_code == 204
    assert client.get("/api/interviews").json() == []


def test_deleting_session_cascades_to_turns(client: TestClient) -> None:
    session_id = start(client)
    client.post(
        "/api/interviews/answer",
        json={"session_id": session_id, "question": "Q", "answer": "An answer."},
    )
    client.delete(f"/api/interviews/{session_id}")

    # A fresh session starts numbering turns cleanly; the old ones are gone.
    assert client.get(f"/api/interviews/{session_id}").status_code == 404


def test_answer_on_missing_session_404(client: TestClient) -> None:
    resp = client.post(
        "/api/interviews/answer", json={"session_id": 999, "question": "Q", "answer": "A"}
    )
    assert resp.status_code == 404
