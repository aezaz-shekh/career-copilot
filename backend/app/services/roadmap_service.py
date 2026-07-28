"""Career roadmap orchestration (Phase 3, Prompt 3.1).

Two LLM calls, grounded in the candidate's resume:

  1. SKILL GAP (low temperature — this is assessment, not creativity): for each
     core skill of the target role, judge the current level ONLY from resume
     evidence and cite the line.
  2. ROADMAP (higher temperature — generative planning): a phased now / 3-month
     / 12-month plan of concrete, generic actions, each mapped to a gap skill.

Like the review pipeline, retrieval (embedding model) happens before generation
(chat model), so there is at most one model swap on the 8 GB machine. Short
resumes are fed whole, skipping embedding entirely.

The generated plan is persisted as a `RoadmapPlan` (verbatim `plan_json`
baseline) plus one editable `RoadmapItem` per action — ticking an action off is
then a single row update, and a regenerate can carry the ticked state across by
matching horizon + action text.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import rag
from app.llm.client import OllamaClient
from app.llm.prompts import render_prompt
from app.models import ResumeVersion, RoadmapItem, RoadmapPlan
from app.models.base import RoadmapHorizon, SourceType
from app.schemas.roadmap import (
    RoadmapActionRead,
    RoadmapPhaseRead,
    RoadmapRead,
    RoadmapResult,
    SkillGapRead,
    SkillGapResult,
)

logger = logging.getLogger(__name__)

RETRIEVE_TOP_K = 6
# A resume this short already fits whole in the prompt, so RAG retrieval would
# only add an embedding call and an embed->chat model swap for no extra grounding.
SKIP_RETRIEVAL_CHARS = 3500

Stage = Literal["retrieve", "skill_gap", "roadmap", "complete"]

# The prompt speaks in now/short/long; the SOW (O4) and the DB enum speak in
# now / 3-month / 12-month. Map between them in exactly one place.
_PHASE_TO_HORIZON = {
    "now": RoadmapHorizon.NOW,
    "short": RoadmapHorizon.THREE_MONTH,
    "long": RoadmapHorizon.TWELVE_MONTH,
}
HORIZON_ORDER = [RoadmapHorizon.NOW, RoadmapHorizon.THREE_MONTH, RoadmapHorizon.TWELVE_MONTH]
HORIZON_LABEL = {
    RoadmapHorizon.NOW: "Now · 0–1 month",
    RoadmapHorizon.THREE_MONTH: "3-Month · 1–3 months",
    RoadmapHorizon.TWELVE_MONTH: "12-Month · 3–12 months",
}


@dataclass
class RoadmapEvent:
    """One progress update from the roadmap pipeline."""

    stage: Stage
    status: Literal["running", "done"]
    index: int
    total: int
    detail: str = ""
    # Populated only on the final ("complete") event.
    skill_gap: SkillGapResult | None = None
    roadmap: RoadmapResult | None = None


async def generate_roadmap(
    session: Session,
    resume: ResumeVersion,
    target_role: str,
    *,
    client: OllamaClient | None = None,
) -> AsyncIterator[RoadmapEvent]:
    """Run the two-call roadmap pipeline, yielding progress before/after each stage.

    The final event carries the raw skill-gap and roadmap results; the caller
    persists them.
    """
    settings = get_settings()
    client = client or OllamaClient()
    total = 3

    # -- Stage 1: retrieve resume evidence for the target role -------------- #
    yield RoadmapEvent("retrieve", "running", 1, total)
    if len(resume.raw_text) <= SKIP_RETRIEVAL_CHARS:
        resume_context = resume.raw_text
        detail = "used full resume"
    else:
        hits = await rag.retrieve(
            session,
            target_role,
            source_ids={SourceType.RESUME: resume.id},
            top_k=RETRIEVE_TOP_K,
            client=client,
        )
        resume_context = rag.build_context_block(hits) or resume.raw_text[:3000]
        detail = f"{len(hits)} resume chunks"
    yield RoadmapEvent("retrieve", "done", 1, total, detail=detail)

    # -- Stage 2: skill gap (assessment -> low temperature) ----------------- #
    yield RoadmapEvent("skill_gap", "running", 2, total)
    gap_prompt = render_prompt("skill_gap", target_role=target_role, resume_chunks=resume_context)
    skill_gap: SkillGapResult = await client.chat(
        [{"role": "user", "content": gap_prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=SkillGapResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    yield RoadmapEvent(
        "skill_gap", "done", 2, total, detail=f"{len(skill_gap.skills)} skills assessed"
    )

    # -- Stage 3: roadmap (planning -> higher temperature) ------------------ #
    yield RoadmapEvent("roadmap", "running", 3, total)
    gaps_json = json.dumps([s.model_dump() for s in skill_gap.skills])
    roadmap_prompt = render_prompt("roadmap", target_role=target_role, gaps_json=gaps_json)
    roadmap: RoadmapResult = await client.chat(
        [{"role": "user", "content": roadmap_prompt}],
        temperature=settings.TEMPERATURE_CREATIVE,
        json_schema=RoadmapResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    n_actions = sum(len(p.actions) for p in roadmap.phases)
    yield RoadmapEvent("roadmap", "done", 3, total, detail=f"{n_actions} actions planned")

    yield RoadmapEvent("complete", "done", total, total, skill_gap=skill_gap, roadmap=roadmap)
    logger.info("Roadmap generated for resume=%d role=%r", resume.id, target_role)


# --------------------------------------------------------------------------- #
# Persistence + assembly
# --------------------------------------------------------------------------- #


def persist_plan(
    session: Session,
    *,
    target_role: str,
    current_profile: str | None,
    skill_gap: SkillGapResult,
    roadmap: RoadmapResult,
    regenerate_plan_id: int | None = None,
) -> RoadmapPlan:
    """Store (or regenerate) a plan and its editable action rows.

    On regenerate, the ticked state of the old actions is carried over by
    matching (horizon, action text). A reworded action loses its tick — that is
    the honest behaviour for a best-effort merge, and better than silently
    marking a changed action as done.
    """
    keep_done: dict[tuple[str, str], bool] = {}
    plan: RoadmapPlan | None = None
    if regenerate_plan_id is not None:
        plan = session.get(RoadmapPlan, regenerate_plan_id)
        if plan is not None:
            for item in plan.items:
                keep_done[(item.horizon.value, item.action)] = item.is_done
            plan.items.clear()  # cascade delete-orphan removes the old rows
            session.flush()

    plan_json = {
        "skill_gap": [s.model_dump() for s in skill_gap.skills],
        "phases": [
            {
                "horizon": _PHASE_TO_HORIZON[p.name].value,
                "actions": [a.model_dump() for a in p.actions],
            }
            for p in roadmap.phases
            if p.name in _PHASE_TO_HORIZON
        ],
    }

    if plan is None:
        plan = RoadmapPlan(
            target_role=target_role, current_profile=current_profile, plan_json=plan_json
        )
        session.add(plan)
    else:
        plan.target_role = target_role
        plan.current_profile = current_profile
        plan.plan_json = plan_json

    for phase in roadmap.phases:
        horizon = _PHASE_TO_HORIZON.get(phase.name)
        if horizon is None:
            continue
        for position, action in enumerate(phase.actions):
            plan.items.append(
                RoadmapItem(
                    horizon=horizon,
                    skill=(action.skill.strip()[:200] or "General"),
                    action=action.action,
                    resource=action.type,  # stored: the action type (course/project/…)
                    is_done=keep_done.get((horizon.value, action.action), False),
                    position=position,
                )
            )

    session.commit()
    session.refresh(plan)
    return plan


def assemble_read(plan: RoadmapPlan) -> RoadmapRead:
    """Build the API view: skill-gap table + three horizon columns of actions.

    Action content (skill/action/type) comes from the editable rows; `why` is
    looked up from the verbatim `plan_json` by (horizon, action), so the row
    table stays lean while the richer rationale is still returned.
    """
    pj = plan.plan_json or {}

    skill_gap: list[SkillGapRead] = []
    for s in pj.get("skill_gap", []):
        required = int(s.get("required_level", 1))
        current = int(s.get("current_level", 1))
        skill_gap.append(
            SkillGapRead(
                skill=s.get("skill", ""),
                required_level=required,
                current_level=current,
                gap=max(required - current, 0),
                priority=s.get("priority", "medium"),
                evidence=s.get("evidence", ""),
            )
        )

    why_by_action: dict[tuple[str, str], str] = {}
    for phase in pj.get("phases", []):
        for action in phase.get("actions", []):
            why_by_action[(phase.get("horizon"), action.get("action"))] = action.get("why", "")

    items_by_horizon: dict[str, list[RoadmapItem]] = {}
    for item in plan.items:
        items_by_horizon.setdefault(item.horizon.value, []).append(item)

    phases: list[RoadmapPhaseRead] = []
    for horizon in HORIZON_ORDER:
        rows = sorted(items_by_horizon.get(horizon.value, []), key=lambda it: it.position)
        actions = [
            RoadmapActionRead(
                item_id=item.id,
                skill=item.skill,
                action=item.action,
                type=item.resource or "practice",
                why=why_by_action.get((horizon.value, item.action), ""),
                done=item.is_done,
            )
            for item in rows
        ]
        phases.append(
            RoadmapPhaseRead(horizon=horizon.value, label=HORIZON_LABEL[horizon], actions=actions)
        )

    return RoadmapRead(
        id=plan.id,
        target_role=plan.target_role,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        skill_gap=skill_gap,
        phases=phases,
    )
