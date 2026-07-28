"""Mock-interview session and turn models (SOW Section 6.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, InterviewMode, enum_column, utcnow
from app.models.resume import JobDescription

# One dict per selected question: {question, type, looks_for, difficulty}.
QuestionBank = list[dict[str, Any]]


class InterviewSession(Base):
    """One mock interview, generated from a job description."""

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # SET NULL rather than CASCADE: deleting a JD should not silently destroy
    # the interview history the user practised with.
    jd_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    mode: Mapped[InterviewMode] = mapped_column(
        enum_column(InterviewMode), default=InterviewMode.TEXT, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # Null while the interview is still in progress.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The selected questions, stored so the session is self-contained for replay
    # and can be resumed even if the browser is refreshed mid-interview.
    question_bank_json: Mapped[QuestionBank | None] = mapped_column(JSON, nullable=True)

    job_description: Mapped[JobDescription | None] = relationship()
    turns: Mapped[list[InterviewTurn]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.id",
    )

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} mode={self.mode.value}>"


class InterviewTurn(Base):
    """A single question/answer exchange, with its rubric scores and feedback."""

    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    # Null between asking the question and receiving the answer.
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recorded per turn: a session can mix spoken and typed answers, and the
    # voice-vs-text scoring comparison (SOW Section 12) needs turn-level detail.
    mode: Mapped[InterviewMode] = mapped_column(
        enum_column(InterviewMode), default=InterviewMode.TEXT, nullable=False
    )

    # Rubric scores as validated JSON, e.g.
    # {"structure": 4, "specificity": 3, "star_adherence": 5}
    scores_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    session: Mapped[InterviewSession] = relationship(back_populates="turns")

    def __repr__(self) -> str:
        return f"<InterviewTurn id={self.id} session_id={self.session_id}>"
