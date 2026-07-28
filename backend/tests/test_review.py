"""Tests for the resume-review pipeline and endpoints.

The LLM is stubbed with a transport that returns a canned answer per stage,
keyed on which prompt arrived, so the real orchestration runs end to end without
Ollama. Retrieval uses the deterministic keyword embedder from the RAG tests.
"""

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
from app.models import JobDescription, ResumeVersion
from app.services import indexing, review_service

DIM = get_settings().EMBED_DIM

RESUME_TEXT = (
    "AARAV SHARMA\naarav@example.com | +91 9812345621\n\n"
    "EXPERIENCE\nWeb Development Intern, Nexus Softwares, May 2025 - July 2025. "
    "Fixed 20 front-end bugs in a React dashboard. Wrote SQL queries.\n\n"
    "EDUCATION\nBCA, Gujarat University, 2023 - 2026\n\n"
    "SKILLS\nPython, SQL, React, Flask, Git\n"
)
PARSED = {
    "contact": {
        "name": "Aarav Sharma",
        "email": "aarav@example.com",
        "phone": "+91 9812345621",
        "location": None,
        "links": [],
    },
    "summary": None,
    "experience": [
        {
            "role": "Web Development Intern",
            "company": "Nexus Softwares",
            "location": None,
            "start_date": "May 2025",
            "end_date": "July 2025",
            "bullets": ["Fixed 20 front-end bugs in a React dashboard.", "Wrote SQL queries."],
        }
    ],
    "education": [
        {
            "degree": "BCA",
            "institution": "Gujarat University",
            "start_date": "2023",
            "end_date": "2026",
            "details": None,
        }
    ],
    "skills": ["Python", "SQL", "React", "Flask", "Git"],
    "projects": [],
    "certifications": [],
}
JD_TEXT = (
    "Junior Python Developer. REQUIRED: Python, FastAPI, REST APIs, SQL, Git, pytest. "
    "NICE TO HAVE: Docker, CI/CD, GitHub Actions, PostgreSQL, AWS."
)

CRITIQUE = {
    "sections": [
        {
            "name": "Experience",
            "strengths": ["Shows a real internship"],
            "issues": [
                {
                    "issue": "Bullets lack metrics",
                    "severity": "medium",
                    "fix": "Add numbers to the SQL work",
                }
            ],
        }
    ]
}
REWRITES = {
    "rewrites": [
        {
            "original": "Wrote SQL queries.",
            "improved": "Wrote optimised SQL powering a weekly operations report.",
            "why": "Adds tool, purpose and cadence",
        }
    ]
}
GAPS = {
    "gaps": [
        {
            "keyword": "FastAPI",
            "importance": "high",
            "present_in_resume": False,
            "suggestion": "Add a FastAPI project",
        },
        {
            "keyword": "Docker",
            "importance": "medium",
            "present_in_resume": False,
            "suggestion": "Containerise a project",
        },
    ]
}


def review_transport() -> httpx.MockTransport:
    """Route each call to the right canned reply based on its content."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            payload = json.loads(request.content)
            vec = [0.0] * DIM
            for i, kw in enumerate(["python", "sql", "react", "flask", "docker", "fastapi"]):
                if kw in payload["input"].lower():
                    vec[i] = 1.0
            vec[DIM - 1] = 0.05
            return httpx.Response(200, json={"embeddings": [vec]})

        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        if "For each resume section" in prompt:
            answer = CRITIQUE
        elif "Rewrite each experience bullet" in prompt:
            answer = REWRITES
        elif "MISSING or WEAK" in prompt:
            answer = GAPS
        else:
            answer = {}
        return httpx.Response(200, json={"message": {"content": json.dumps(answer)}})

    return httpx.MockTransport(handler)


def stub_client() -> OllamaClient:
    return OllamaClient(transport=review_transport())


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'review.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    # Auto-indexing on save uses the stub embedder.
    real = indexing.index_document

    async def patched(session, source_type, source_id, text, *, client=None):
        return await real(session, source_type, source_id, text, client=stub_client())

    monkeypatch.setattr("app.routers.resumes.index_document", patched)
    monkeypatch.setattr("app.routers.jds.index_document", patched)
    # The streamed review builds its own client; point it at the stub.
    monkeypatch.setattr(review_service, "OllamaClient", stub_client)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def seed(client: TestClient) -> tuple[int, int]:
    r = client.post(
        "/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT, "parsed_json": PARSED}
    )
    j = client.post("/api/jds", json={"title": "Junior Python Developer", "raw_text": JD_TEXT})
    return r.json()["id"], j.json()["id"]


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for frame in text.split("\n\n"):
        event, data = None, None
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event and data is not None:
            events.append((event, data))
    return events


# --------------------------------------------------------------------------- #
# Service-level
# --------------------------------------------------------------------------- #


async def test_generate_review_runs_all_stages(tmp_path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 's.db'}")
    init_db(engine)
    from app.llm import rag
    from app.models.base import SourceType

    with Session(engine) as session:
        resume = ResumeVersion(title="v1", raw_text=RESUME_TEXT, parsed_json=PARSED)
        jd = JobDescription(title="Junior Python Developer", raw_text=JD_TEXT)
        session.add_all([resume, jd])
        session.commit()
        await rag.index_source(
            session, SourceType.RESUME, resume.id, RESUME_TEXT, client=stub_client()
        )
        await rag.index_source(session, SourceType.JD, jd.id, JD_TEXT, client=stub_client())

        stages = []
        report = None
        async for ev in review_service.generate_review(session, resume, jd, client=stub_client()):
            stages.append((ev.stage, ev.status))
            if ev.report is not None:
                report = ev.report

    assert ("retrieve", "running") in stages
    assert ("critique", "done") in stages
    assert ("rewrites", "done") in stages
    assert ("keyword_gap", "done") in stages
    assert ("ats", "done") in stages
    assert stages[-1] == ("complete", "done")

    assert report is not None
    assert report.sections[0].name == "Experience"
    assert report.rewrites[0].improved != report.rewrites[0].original
    assert any(g.keyword == "FastAPI" for g in report.gaps)
    assert report.ats.total == 5
    engine.dispose()


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


def test_review_streams_progress_then_stores_report(client: TestClient) -> None:
    resume_id, jd_id = seed(client)

    response = client.post("/api/review", json={"resume_id": resume_id, "jd_id": jd_id})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)

    steps = [d["stage"] for e, d in events if e == "step"]
    assert "critique" in steps and "keyword_gap" in steps and "ats" in steps

    done = [d for e, d in events if e == "done"]
    assert len(done) == 1
    report_id = done[0]["report_id"]
    assert done[0]["report"]["gaps"][0]["keyword"] == "FastAPI"

    # The report was persisted and is retrievable.
    fetched = client.get(f"/api/review/{report_id}")
    assert fetched.status_code == 200
    assert fetched.json()["report_json"]["ats"]["total"] == 5


def test_review_lists_and_deletes(client: TestClient) -> None:
    resume_id, jd_id = seed(client)
    client.post("/api/review", json={"resume_id": resume_id, "jd_id": jd_id})

    listing = client.get("/api/review").json()
    assert len(listing) == 1
    review_id = listing[0]["id"]

    assert client.delete(f"/api/review/{review_id}").status_code == 204
    assert client.get("/api/review").json() == []


def test_review_404_for_unknown_resume(client: TestClient) -> None:
    _, jd_id = seed(client)
    response = client.post("/api/review", json={"resume_id": 999, "jd_id": jd_id})

    assert response.status_code == 404
    assert "hint" in response.json()["detail"]


def test_deleting_resume_cascades_to_its_reviews(client: TestClient) -> None:
    resume_id, jd_id = seed(client)
    client.post("/api/review", json={"resume_id": resume_id, "jd_id": jd_id})
    assert len(client.get("/api/review").json()) == 1

    client.delete(f"/api/resumes/{resume_id}")

    assert client.get("/api/review").json() == []
