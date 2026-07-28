"""API tests for resume and job-description ingestion.

The database is redirected to a temp file and the LLM is stubbed, so these run
fast and need neither Ollama nor the user's real data.
"""

from __future__ import annotations

import json

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import create_db_engine, get_session, init_db
from app.llm.client import OllamaClient, OllamaDownError
from app.llm.prompts import PromptNotFoundError, load_prompt, render_prompt
from app.main import app
from app.schemas.resume import ParsedResume
from app.services import resume_service

RESUME_TEXT = (
    "AARAV SHARMA\naarav@example.com\n\n"
    "EDUCATION\nBCA, Gujarat University, 2023 - 2026\n\n"
    "SKILLS\nPython, SQL, React\n\n"
    "EXPERIENCE\nWeb Development Intern, Nexus Softwares, May 2025 - July 2025\n"
    "Fixed more than twenty front-end defects in a React dashboard.\n"
)

MODEL_OUTPUT = {
    "contact": {
        "name": "Aarav Sharma",
        "email": "aarav@example.com",
        "phone": None,
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
            "bullets": ["Fixed more than twenty front-end defects in a React dashboard."],
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
    "skills": ["Python", "SQL", "React"],
    "projects": [],
    "certifications": [],
}


@pytest.fixture
def client(tmp_path) -> TestClient:
    """A TestClient whose database is a throwaway file."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'api.db'}")
    init_db(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 560, 780), text, fontsize=10)
    data = document.tobytes()
    document.close()
    return data


# --------------------------------------------------------------------------- #
# Upload
# --------------------------------------------------------------------------- #


def test_upload_pdf_returns_text_and_quality(client: TestClient) -> None:
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert "AARAV SHARMA" in body["raw_text"]
    assert body["quality"]["parser_used"] == "pymupdf"
    assert body["quality"]["fallback_used"] is False
    assert body["quality"]["is_usable"] is True


def test_upload_txt_returns_text(client: TestClient) -> None:
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("resume.txt", RESUME_TEXT.encode(), "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["quality"]["parser_used"] == "plaintext"


def test_upload_rejects_unsupported_type_with_a_hint(client: TestClient) -> None:
    response = client.post(
        "/api/resumes/upload", files={"file": ("resume.docx", b"PK\x03\x04", "application/octet")}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "PDF" in detail["hint"]  # actionable, not a stack trace


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    huge = b"x" * (6 * 1024 * 1024)
    response = client.post(
        "/api/resumes/upload", files={"file": ("resume.pdf", huge, "application/pdf")}
    )

    assert response.status_code == 413
    assert "hint" in response.json()["detail"]


def test_upload_persists_nothing(client: TestClient) -> None:
    """Review comes before storage — SOW Section 11."""
    client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT), "application/pdf")},
    )

    assert client.get("/api/resumes").json() == []


# --------------------------------------------------------------------------- #
# Structuring  (required test #2)
# --------------------------------------------------------------------------- #


def stub_transport(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": json.dumps(payload)}}
        )

    return httpx.MockTransport(handler)


async def test_structuring_output_validates_against_the_schema() -> None:
    """The model's JSON must come back as a validated ParsedResume."""
    client = OllamaClient(transport=stub_transport(MODEL_OUTPUT))

    parsed, elapsed_ms = await resume_service.structure_resume(RESUME_TEXT, client=client)

    assert isinstance(parsed, ParsedResume)
    assert parsed.contact.name == "Aarav Sharma"
    assert parsed.contact.email == "aarav@example.com"
    assert parsed.skills == ["Python", "SQL", "React"]
    assert parsed.experience[0].company == "Nexus Softwares"
    assert parsed.experience[0].bullets[0].startswith("Fixed more than twenty")
    assert parsed.education[0].degree == "BCA"
    assert parsed.projects == []  # absent section stays empty, never invented
    assert elapsed_ms >= 0


async def test_structuring_sends_the_schema_and_the_resume_text() -> None:
    """Ollama must receive the JSON Schema so sampling is constrained."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": json.dumps(MODEL_OUTPUT)}}
        )

    client = OllamaClient(transport=httpx.MockTransport(handler))
    await resume_service.structure_resume(RESUME_TEXT, client=client)

    assert captured["format"] == ParsedResume.model_json_schema()
    assert "AARAV SHARMA" in captured["messages"][0]["content"]
    # Extraction, not creativity: the cold temperature must be used.
    assert captured["options"]["temperature"] == 0.2


async def test_structuring_repairs_incomplete_model_output() -> None:
    """A 3B model dropping a required key must not fail the request."""
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        content = json.dumps({"contact": {"name": "Aarav"}, "experience": [{"company": "X"}]})
        if len(calls) > 1:
            content = json.dumps(MODEL_OUTPUT)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    parsed, _ = await resume_service.structure_resume(RESUME_TEXT, client=client)

    assert len(calls) == 2  # first attempt was repaired
    assert parsed.contact.name == "Aarav Sharma"


def test_structure_endpoint_reports_ollama_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(*args, **kwargs):
        raise OllamaDownError("Could not connect", hint="Run: ollama serve")

    monkeypatch.setattr(resume_service, "structure_resume", failing)

    response = client.post("/api/resumes/structure", json={"raw_text": RESUME_TEXT})

    assert response.status_code == 503
    assert "ollama serve" in response.json()["detail"]["hint"]


def test_structure_endpoint_rejects_trivial_input(client: TestClient) -> None:
    assert client.post("/api/resumes/structure", json={"raw_text": "hi"}).status_code == 422


# --------------------------------------------------------------------------- #
# Prompt templates
# --------------------------------------------------------------------------- #


def test_resume_parser_prompt_exists_and_substitutes() -> None:
    rendered = render_prompt("resume_parser", resume_text=RESUME_TEXT)

    assert "AARAV SHARMA" in rendered
    assert "$resume_text" not in rendered


def test_prompt_loader_resolves_to_the_highest_version() -> None:
    """An unpinned load picks the newest file — v2 exists, so it must win."""
    assert load_prompt("resume_parser") == load_prompt("resume_parser", version=2)


def test_structuring_uses_the_pinned_prompt_version() -> None:
    """v1 measured better than v2 (see prompts/README.md), so it stays pinned.

    Without this test, adding a v3 file would silently change model behaviour.
    """
    assert resume_service.PROMPT_VERSION == 1

    rendered = render_prompt(
        resume_service.PROMPT_NAME, version=resume_service.PROMPT_VERSION, resume_text="x"
    )
    assert rendered == render_prompt("resume_parser", version=1, resume_text="x")
    assert rendered != render_prompt("resume_parser", version=2, resume_text="x")


def test_missing_prompt_raises_a_clear_error() -> None:
    with pytest.raises(PromptNotFoundError, match="no_such_prompt"):
        load_prompt("no_such_prompt")


def test_dollar_sign_in_resume_text_does_not_break_rendering() -> None:
    """safe_substitute: a salary line like '$50,000' must not raise."""
    rendered = render_prompt("resume_parser", resume_text="Managed a $50,000 budget")

    assert "$50,000" in rendered


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def test_save_and_fetch_resume_version(client: TestClient) -> None:
    created = client.post(
        "/api/resumes",
        json={
            "title": "Tailored for TechNova",
            "raw_text": RESUME_TEXT,
            "parsed_json": MODEL_OUTPUT,
        },
    )

    assert created.status_code == 201
    resume_id = created.json()["id"]

    fetched = client.get(f"/api/resumes/{resume_id}").json()
    assert fetched["title"] == "Tailored for TechNova"
    assert fetched["parsed_json"]["contact"]["name"] == "Aarav Sharma"

    listing = client.get("/api/resumes").json()
    assert len(listing) == 1
    assert "raw_text" not in listing[0]  # summary shape stays light


def test_saving_edited_sections_keeps_the_users_edits(client: TestClient) -> None:
    """The whole point of the review step: what the user typed is what is stored."""
    edited = dict(MODEL_OUTPUT)
    edited["skills"] = ["Python", "SQL", "React", "FastAPI (corrected by hand)"]

    created = client.post(
        "/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT, "parsed_json": edited}
    )

    stored = client.get(f"/api/resumes/{created.json()['id']}").json()
    assert "FastAPI (corrected by hand)" in stored["parsed_json"]["skills"]


def test_versions_accumulate_rather_than_overwrite(client: TestClient) -> None:
    for title in ("Original", "Tailored for TechNova"):
        client.post("/api/resumes", json={"title": title, "raw_text": RESUME_TEXT})

    assert len(client.get("/api/resumes").json()) == 2


def test_missing_resume_returns_404_with_a_hint(client: TestClient) -> None:
    response = client.get("/api/resumes/999")

    assert response.status_code == 404
    assert "hint" in response.json()["detail"]


def test_delete_resume(client: TestClient) -> None:
    created = client.post("/api/resumes", json={"title": "v1", "raw_text": RESUME_TEXT})

    assert client.delete(f"/api/resumes/{created.json()['id']}").status_code == 204
    assert client.get("/api/resumes").json() == []


# --------------------------------------------------------------------------- #
# Job descriptions
# --------------------------------------------------------------------------- #


def test_save_and_fetch_job_description(client: TestClient) -> None:
    created = client.post(
        "/api/jds",
        json={
            "title": "Junior Python Developer",
            "company": "TechNova",
            "raw_text": "We need Python, FastAPI, Docker and CI/CD experience.",
        },
    )

    assert created.status_code == 201
    jd_id = created.json()["id"]

    fetched = client.get(f"/api/jds/{jd_id}").json()
    assert fetched["company"] == "TechNova"
    # Stored verbatim: gap analysis needs the employer's own wording.
    assert "Docker" in fetched["raw_text"]


def test_jd_requires_meaningful_text(client: TestClient) -> None:
    response = client.post("/api/jds", json={"title": "Dev", "raw_text": "too short"})

    assert response.status_code == 422


def test_jd_company_is_optional(client: TestClient) -> None:
    response = client.post(
        "/api/jds",
        json={"title": "Backend Developer", "raw_text": "A" * 50},
    )

    assert response.status_code == 201
    assert response.json()["company"] is None


def test_delete_job_description(client: TestClient) -> None:
    created = client.post("/api/jds", json={"title": "Dev", "raw_text": "A" * 50})

    assert client.delete(f"/api/jds/{created.json()['id']}").status_code == 204
    assert client.get("/api/jds").json() == []
