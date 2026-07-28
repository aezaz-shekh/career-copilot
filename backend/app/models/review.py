"""Stored resume-review reports (Phase 1, the main feature).

The SOW entity list (Section 6.3) predates this feature and does not name a
review table, but Prompt 1.3 requires the combined report to be stored so a user
can reopen a critique without paying the multi-minute regeneration cost again.
The whole report is kept as one JSON document rather than shredded across tables:
it is always read and written as a unit, it is never queried field-by-field, and
its shape is owned by a Pydantic schema that can evolve without a migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow
from app.models.resume import JobDescription, ResumeVersion


class ReviewReport(Base):
    """One resume-vs-JD review: section critique, rewrites, gaps, and ATS checks."""

    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # A report is meaningless without both documents, so it is removed when
    # either is deleted (unlike interview history, which outlives its JD).
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jd_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The full report: {"sections": [...], "rewrites": [...], "gaps": [...],
    # "ats": {...}}. Validated against schemas.review.ReviewReport before storage.
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    resume: Mapped[ResumeVersion] = relationship()
    job_description: Mapped[JobDescription] = relationship()

    def __repr__(self) -> str:
        return f"<ReviewReport id={self.id} resume={self.resume_id} jd={self.jd_id}>"
