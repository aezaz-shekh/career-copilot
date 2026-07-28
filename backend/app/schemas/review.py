"""Schemas for the resume-review feature (Phase 1, Prompt 1.3).

The three `*Result` models are handed to Ollama's `format` parameter, so their
shape must match the JSON in the C2/C3/C4 prompt templates exactly — the model
is constrained to produce what these validate. `ReviewReport` is the combined
document that gets stored and returned.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["high", "medium", "low"]
Importance = Literal["high", "medium", "low"]


# --------------------------------------------------------------------------- #
# 1. Section critique  (prompts/section_critique_v1.txt)
# --------------------------------------------------------------------------- #


class SectionIssue(BaseModel):
    issue: str = Field(description="A specific problem, referencing actual resume text")
    severity: Severity
    fix: str = Field(description="A concrete, actionable fix")


class SectionCritique(BaseModel):
    name: str = Field(description="Resume section name, e.g. Experience, Skills")
    strengths: list[str] = Field(default_factory=list)
    issues: list[SectionIssue] = Field(default_factory=list)


class SectionCritiqueResult(BaseModel):
    """Ollama-constrained output for the critique call."""

    sections: list[SectionCritique] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 2. Bullet rewrites  (prompts/bullet_rewrite_v1.txt)
# --------------------------------------------------------------------------- #


class BulletRewrite(BaseModel):
    original: str
    improved: str = Field(description="Stronger rewrite: verb + action + skill + result")
    why: str = Field(description="Why the rewrite is stronger for this JD")


class BulletRewriteResult(BaseModel):
    rewrites: list[BulletRewrite] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 3. Keyword gap  (prompts/keyword_gap_v1.txt)
# --------------------------------------------------------------------------- #


class KeywordGap(BaseModel):
    keyword: str = Field(description="A skill/keyword the JD asks for")
    importance: Importance
    present_in_resume: bool = Field(description="False if missing, i.e. a real gap")
    suggestion: str = Field(description="Where/how to add it honestly")


class KeywordGapResult(BaseModel):
    gaps: list[KeywordGap] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 4. ATS checklist  (deterministic — see services/ats.py)
# --------------------------------------------------------------------------- #


class AtsCheck(BaseModel):
    name: str = Field(description="What was checked")
    passed: bool
    detail: str = Field(description="Plain-language result the user can act on")


class AtsChecklist(BaseModel):
    checks: list[AtsCheck] = Field(default_factory=list)
    passed_count: int = 0
    total: int = 0


# --------------------------------------------------------------------------- #
# Combined report
# --------------------------------------------------------------------------- #


class ReviewReport(BaseModel):
    """The full report: what gets stored and returned to the UI."""

    model_config = ConfigDict(extra="ignore")

    sections: list[SectionCritique] = Field(default_factory=list)
    rewrites: list[BulletRewrite] = Field(default_factory=list)
    gaps: list[KeywordGap] = Field(default_factory=list)
    ats: AtsChecklist = Field(default_factory=AtsChecklist)


# --------------------------------------------------------------------------- #
# API request / response
# --------------------------------------------------------------------------- #


class ReviewRequest(BaseModel):
    resume_id: int
    jd_id: int


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resume_id: int
    jd_id: int
    report_json: ReviewReport
    created_at: datetime


class ReviewSummary(BaseModel):
    """Listing shape — omits the report body to keep the list light."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    resume_id: int
    jd_id: int
    created_at: datetime
