"""Schemas for the career roadmap feature (Phase 3, Prompt 3.1).

Two LLM-constrained result models match the JSON in the prompt templates:

  - `SkillGapResult`  ← prompts/skill_gap_v1.txt
  - `RoadmapResult`   ← prompts/roadmap_v2.txt

The `*Read` models are the assembled API shape: a skill-gap table plus three
horizon columns of checkable actions, built from the stored `RoadmapPlan` and
its editable `RoadmapItem` rows. `gap` is computed here (required - current)
rather than trusted from the model, so the table is always internally
consistent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Priority = Literal["high", "medium", "low"]
ActionType = Literal["course", "project", "cert", "practice"]
PhaseName = Literal["now", "short", "long"]
Level = Annotated[int, Field(ge=1, le=5)]


# --------------------------------------------------------------------------- #
# 1. Skill gap  (LLM-constrained — prompts/skill_gap_v1.txt)
# --------------------------------------------------------------------------- #


class SkillGap(BaseModel):
    skill: str = Field(description="A core skill the target role requires")
    required_level: Level = Field(description="1-5, how strong the role needs this")
    current_level: Level = Field(description="1-5, judged ONLY from resume evidence")
    priority: Priority
    evidence: str = Field(description="Resume line justifying current_level, or 'not found'")


class SkillGapResult(BaseModel):
    """Ollama-constrained output for the skill-gap call."""

    skills: list[SkillGap] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 2. Roadmap  (LLM-constrained — prompts/roadmap_v2.txt)
# --------------------------------------------------------------------------- #


class RoadmapActionGen(BaseModel):
    skill: str = Field(description="Which listed gap skill this action builds")
    action: str = Field(description="A concrete, generic action — no paid product names")
    type: ActionType
    why: str = Field(description="Why this action matters for the target role")


class RoadmapPhaseGen(BaseModel):
    name: PhaseName
    actions: list[RoadmapActionGen] = Field(default_factory=list)


class RoadmapResult(BaseModel):
    """Ollama-constrained output for the roadmap call."""

    phases: list[RoadmapPhaseGen] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# API request
# --------------------------------------------------------------------------- #


class RoadmapRequest(BaseModel):
    resume_id: int
    target_role: str = Field(min_length=1, max_length=200)
    # When set, regenerate this existing plan, carrying over which actions the
    # user has already ticked off (matched by horizon + action text).
    regenerate_plan_id: int | None = None


# --------------------------------------------------------------------------- #
# API read (assembled from RoadmapPlan + RoadmapItem rows)
# --------------------------------------------------------------------------- #


class SkillGapRead(BaseModel):
    skill: str
    required_level: int
    current_level: int
    gap: int
    priority: str
    evidence: str


class RoadmapActionRead(BaseModel):
    item_id: int
    skill: str
    action: str
    type: str
    why: str
    done: bool


class RoadmapPhaseRead(BaseModel):
    horizon: str = Field(description="Stored enum value: now / 3_month / 12_month")
    label: str = Field(description="Human label for the column header")
    actions: list[RoadmapActionRead] = Field(default_factory=list)


class RoadmapRead(BaseModel):
    id: int
    target_role: str
    created_at: datetime
    updated_at: datetime
    skill_gap: list[SkillGapRead] = Field(default_factory=list)
    phases: list[RoadmapPhaseRead] = Field(default_factory=list)


class RoadmapSummary(BaseModel):
    """Listing shape — counts instead of the full body."""

    id: int
    target_role: str
    created_at: datetime
    updated_at: datetime
    done_count: int
    total_count: int


class RoadmapItemUpdate(BaseModel):
    done: bool
