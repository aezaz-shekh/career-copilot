"""Resume and job-description models (SOW Section 6.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class ResumeVersion(Base):
    """One uploaded or edited version of the user's resume.

    Versions are kept rather than overwritten so the user can compare a tailored
    resume against the original (SOW Section 4.1, module 1: "resume version
    history").
    """

    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured sections produced by the parser (contact, experience, skills...).
    # Null until parsing succeeds, so a failed parse still preserves raw_text and
    # the user can fall back to manual editing (SOW Section 11, PDF risk).
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ResumeVersion id={self.id} title={self.title!r}>"


class JobDescription(Base):
    """A target job description pasted in by the user."""

    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<JobDescription id={self.id} title={self.title!r}>"
