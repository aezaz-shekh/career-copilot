"""Schemas for interview prep (Phase 2).

`QuestionBankResult` is handed to Ollama's `format` parameter, so its shape must
match the JSON in prompts/question_gen_v1.txt (C5). Field name `looks_for`
matches that template; the model is constrained to the schema regardless of the
prompt wording, so the two are kept aligned on purpose.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal["behavioral", "technical"]
# 1 = warm-up, 2 = core, 3 = stretch. Constrained so the model cannot invent a 4.
Difficulty = Annotated[int, Field(ge=1, le=3)]


class InterviewQuestion(BaseModel):
    question: str = Field(description="The interview question, tied to the JD and resume")
    type: QuestionType
    looks_for: str = Field(description="What a good answer demonstrates")
    difficulty: Difficulty = Field(description="1 easy, 2 medium, 3 hard")


class QuestionBankResult(BaseModel):
    """Ollama-constrained output for the question generator."""

    questions: list[InterviewQuestion] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# API request / response
# --------------------------------------------------------------------------- #


class QuestionBankRequest(BaseModel):
    # Two ways to generate:
    #   resume_id + jd_id      → grounded in the candidate's own resume (RAG)
    #   job_title (+ topics)   → general to a chosen role, no resume needed
    resume_id: int | None = None
    jd_id: int | None = None
    job_title: str | None = Field(default=None, max_length=200)
    topics: str | None = Field(default=None, max_length=2000)
    n_behavioral: int = Field(default=3, ge=1, le=10)
    n_technical: int = Field(default=3, ge=1, le=10)


class QuestionBankResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[InterviewQuestion]
    behavioral_count: int
    technical_count: int
    elapsed_ms: int = Field(description="Generation time, so slow hardware is visible in the UI")


# --------------------------------------------------------------------------- #
# Scoring (prompts/answer_scoring_v1.txt — C6, temperature 0.2)
# --------------------------------------------------------------------------- #

Score = Annotated[int, Field(ge=1, le=5)]
RUBRIC_DIMENSIONS = ("structure", "specificity", "star_adherence", "relevance")


class AnswerScores(BaseModel):
    structure: Score
    specificity: Score
    star_adherence: Score
    relevance: Score


class AnswerFeedback(BaseModel):
    structure: str
    specificity: str
    star_adherence: str
    relevance: str


class ScoringResult(BaseModel):
    """Ollama-constrained output for the answer-scoring call."""

    scores: AnswerScores
    feedback: AnswerFeedback
    improvement_tip: str


# --------------------------------------------------------------------------- #
# Follow-up decision (prompts/followup_decider_v1.txt — C7)
# --------------------------------------------------------------------------- #


class FollowupResult(BaseModel):
    needs_followup: bool
    followup_question: str | None = None


# --------------------------------------------------------------------------- #
# Interview flow API
# --------------------------------------------------------------------------- #


class StartInterviewRequest(BaseModel):
    jd_id: int | None = None
    mode: Literal["text", "voice"] = "text"
    questions: list[InterviewQuestion] = Field(min_length=1)


class StartInterviewResponse(BaseModel):
    session_id: int
    mode: str
    questions: list[InterviewQuestion]


class AnswerRequest(BaseModel):
    session_id: int
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=8000)
    is_followup: bool = False


class AnswerResponse(BaseModel):
    """Returned after an answer is scored.

    Scores are deliberately NOT included: they are stored per turn but only
    revealed once the session ends, which is more like a real interview.
    """

    turn_id: int
    needs_followup: bool
    followup_question: str | None = None


class TurnRead(BaseModel):
    id: int
    question: str
    answer: str | None
    is_followup: bool = False
    scores: AnswerScores | None = None
    feedback: AnswerFeedback | None = None
    improvement_tip: str | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    answered: int
    averages: dict[str, float]
    overall_average: float
    strengths: list[str]
    improvement_areas: list[str]
    tips: list[str]


class SessionRead(BaseModel):
    id: int
    jd_id: int | None
    mode: str
    started_at: datetime
    ended_at: datetime | None
    turns: list[TurnRead]
    summary: SessionSummary | None = None


class SessionListItem(BaseModel):
    id: int
    jd_id: int | None
    mode: str
    started_at: datetime
    ended_at: datetime | None
    turn_count: int
