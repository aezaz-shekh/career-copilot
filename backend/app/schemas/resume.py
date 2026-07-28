"""Schemas for resume ingestion, structuring, and storage.

`ParsedResume` is both the API response shape *and* the JSON Schema handed to
Ollama's `format` parameter, so the model is constrained to produce exactly what
the application validates. One definition, no drift.

Field descriptions are deliberately written as instructions: they are part of
the JSON Schema the model sees, so they do real work in guiding a 3B model.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactInfo(BaseModel):
    """Contact details found in the resume header."""

    name: str | None = Field(default=None, description="Full name of the candidate")
    email: str | None = Field(default=None, description="Email address, or null if absent")
    phone: str | None = Field(default=None, description="Phone number, or null if absent")
    location: str | None = Field(default=None, description="City and state or country")
    links: list[str] = Field(default_factory=list, description="Portfolio, GitHub or LinkedIn URLs")


class ExperienceItem(BaseModel):
    """One job, internship, or period of employment."""

    role: str = Field(description="Job title exactly as written")
    company: str | None = Field(default=None, description="Employer name")
    location: str | None = Field(default=None, description="Where the job was based")
    start_date: str | None = Field(default=None, description="Start date as written, e.g. May 2025")
    end_date: str | None = Field(default=None, description="End date as written, or Present")
    bullets: list[str] = Field(
        default_factory=list,
        description="Achievement bullets copied close to verbatim, keeping all numbers",
    )


class EducationItem(BaseModel):
    """One degree, diploma, or course of study."""

    degree: str = Field(description="Qualification, e.g. Bachelor of Computer Applications")
    institution: str | None = Field(default=None, description="School or university name")
    start_date: str | None = Field(default=None, description="Start date as written")
    end_date: str | None = Field(default=None, description="End or expected date as written")
    details: str | None = Field(default=None, description="CGPA, percentage or coursework")


class ProjectItem(BaseModel):
    """One academic or personal project."""

    name: str = Field(description="Project name")
    description: str | None = Field(default=None, description="One-line summary if present")
    bullets: list[str] = Field(
        default_factory=list, description="Detail bullets copied close to verbatim"
    )
    technologies: list[str] = Field(
        default_factory=list, description="Technologies named for this project"
    )


class ParsedResume(BaseModel):
    """A resume broken into structured sections.

    Every list defaults to empty and every scalar to null, because an absent
    section is normal — a fresher's resume often has no work experience — and
    the parser prompt forbids inventing content to fill a gap.
    """

    model_config = ConfigDict(extra="ignore")

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = Field(default=None, description="Professional summary or objective")
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(
        default_factory=list,
        description="Flat list of individual skills, category labels removed",
    )
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Extraction (step 1: file -> raw text)
# --------------------------------------------------------------------------- #


class ExtractionQuality(BaseModel):
    """How trustworthy the extracted text looks.

    Surfaced to the user rather than hidden, because a low score is exactly when
    they need to be told to check the text before generating anything.
    """

    is_usable: bool = Field(description="False when the text looks broken or empty")
    parser_used: str = Field(description="pymupdf, pdfplumber, or plaintext")
    fallback_used: bool = Field(description="True if the primary parser was rejected")
    character_count: int
    page_count: int
    warnings: list[str] = Field(
        default_factory=list, description="Plain-language problems found in the text"
    )


class UploadResponse(BaseModel):
    """Result of uploading a resume file. Nothing is persisted at this stage."""

    raw_text: str
    filename: str
    quality: ExtractionQuality


# --------------------------------------------------------------------------- #
# Structuring (step 2: raw text -> sections)
# --------------------------------------------------------------------------- #


class StructureRequest(BaseModel):
    """Raw resume text to be broken into sections by the local model."""

    raw_text: str = Field(min_length=20, max_length=60_000)


class StructureResponse(BaseModel):
    parsed: ParsedResume
    elapsed_ms: int = Field(description="Generation time, so slow hardware is visible in the UI")
    repaired: bool = Field(
        default=False, description="True if the model needed a schema-repair retry"
    )


# --------------------------------------------------------------------------- #
# Persistence (step 3: save the user-reviewed version)
# --------------------------------------------------------------------------- #


class ResumeCreate(BaseModel):
    """Save a resume version after the user has reviewed and edited it."""

    title: str = Field(min_length=1, max_length=200)
    raw_text: str = Field(min_length=1)
    parsed_json: ParsedResume | None = None


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    raw_text: str
    parsed_json: ParsedResume | None = None
    created_at: datetime


class ResumeSummary(BaseModel):
    """Listing shape — omits the full text so the list endpoint stays light."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Job descriptions
# --------------------------------------------------------------------------- #


class JobDescriptionCreate(BaseModel):
    """A pasted job description. Saved exactly as provided, never scraped."""

    title: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    raw_text: str = Field(min_length=20)


class JobDescriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None
    raw_text: str
    created_at: datetime


class JobDescriptionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None
    created_at: datetime
