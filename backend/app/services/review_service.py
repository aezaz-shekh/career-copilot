"""Resume-review orchestration (Phase 1, Prompt 1.3).

Runs the four review stages and yields progress as it goes, so the UI can show a
stepper during what is a multi-minute operation on CPU-only hardware.

ORDER MATTERS FOR PERFORMANCE. Embedding and chat use different Ollama models,
and on 8 GB RAM loading one evicts the other (~15 s reload — see the model-swap
note). So this does ALL retrieval first (embedding model resident), then ALL
generation (chat model resident). That is exactly one model swap for the whole
review, instead of one per stage.

Stages:
  1. retrieve — embed two queries, pull the relevant resume and JD chunks
  2. critique — C2, low temperature (analysis, not creativity)
  3. rewrites — C3, high temperature (creative drafting, but never fabricating)
  4. keyword_gap — C4, low temperature (analysis)
  5. ats — deterministic, instant (services/ats.py)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import rag
from app.llm.client import OllamaClient
from app.llm.prompts import render_prompt
from app.models import JobDescription, ResumeVersion
from app.models.base import SourceType
from app.schemas.resume import ParsedResume
from app.schemas.review import (
    BulletRewriteResult,
    KeywordGapResult,
    ReviewReport,
    SectionCritiqueResult,
)
from app.services.ats import run_ats_checks

logger = logging.getLogger(__name__)

Stage = Literal["retrieve", "critique", "rewrites", "keyword_gap", "ats", "complete"]

# Cap how many bullets we send to the rewrite call. A dozen is plenty for a
# fresher's resume and keeps that generation from ballooning to many minutes.
MAX_BULLETS = 12
RETRIEVE_TOP_K = 6


@dataclass
class ReviewEvent:
    """One progress update from the review pipeline."""

    stage: Stage
    status: Literal["running", "done"]
    index: int  # 1-based position in the pipeline
    total: int
    report: ReviewReport | None = None  # populated only on the final event
    detail: str = ""


@dataclass
class _Bundle:
    """Working state threaded through the stages."""

    resume: ResumeVersion
    jd: JobDescription
    parsed: ParsedResume | None
    resume_context: str = ""
    jd_context: str = ""
    report: ReviewReport = field(default_factory=ReviewReport)


def _extract_bullets(parsed: ParsedResume | None) -> list[str]:
    """Pull experience bullets from the parsed resume, capped for latency."""
    if not parsed:
        return []
    bullets: list[str] = []
    for role in parsed.experience:
        bullets.extend(bullet for bullet in role.bullets if bullet.strip())
    return bullets[:MAX_BULLETS]


async def generate_review(
    session: Session,
    resume: ResumeVersion,
    jd: JobDescription,
    *,
    client: OllamaClient | None = None,
) -> AsyncIterator[ReviewEvent]:
    """Run the review, yielding a ReviewEvent before and after each stage.

    The final event has stage="complete" and carries the assembled report. The
    caller is responsible for persisting it.
    """
    settings = get_settings()
    client = client or OllamaClient()

    parsed = ParsedResume.model_validate(resume.parsed_json) if resume.parsed_json else None
    bundle = _Bundle(resume=resume, jd=jd, parsed=parsed)

    total = 5

    # -- Stage 1: retrieval (all embedding happens here) -------------------- #
    yield ReviewEvent("retrieve", "running", 1, total)
    # Use the JD as the query for both retrievals: it surfaces the resume
    # evidence relevant to this job, and the requirement-dense JD chunks.
    query = f"{jd.title}\n{jd.raw_text}"[:4000]
    resume_hits = await rag.retrieve(
        session,
        query,
        source_ids={SourceType.RESUME: resume.id},
        top_k=RETRIEVE_TOP_K,
        client=client,
    )
    jd_hits = await rag.retrieve(
        session, query, source_ids={SourceType.JD: jd.id}, top_k=RETRIEVE_TOP_K, client=client
    )
    bundle.resume_context = rag.build_context_block(resume_hits) or resume.raw_text[:3000]
    bundle.jd_context = rag.build_context_block(jd_hits) or jd.raw_text[:3000]
    yield ReviewEvent(
        "retrieve",
        "done",
        1,
        total,
        detail=f"{len(resume_hits)} resume + {len(jd_hits)} JD chunks",
    )

    # -- Stage 2: section critique (C2, analysis -> low temp) --------------- #
    yield ReviewEvent("critique", "running", 2, total)
    critique_prompt = render_prompt(
        "section_critique", jd_chunks=bundle.jd_context, resume_chunks=bundle.resume_context
    )
    critique: SectionCritiqueResult = await client.chat(
        [{"role": "user", "content": critique_prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=SectionCritiqueResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    bundle.report.sections = critique.sections
    yield ReviewEvent("critique", "done", 2, total, detail=f"{len(critique.sections)} sections")

    # -- Stage 3: bullet rewrites (C3, creative -> high temp) --------------- #
    yield ReviewEvent("rewrites", "running", 3, total)
    bullets = _extract_bullets(parsed)
    if bullets:
        import json

        rewrite_prompt = render_prompt(
            "bullet_rewrite", jd_chunks=bundle.jd_context, bullets_json=json.dumps(bullets)
        )
        rewrites: BulletRewriteResult = await client.chat(
            [{"role": "user", "content": rewrite_prompt}],
            temperature=settings.TEMPERATURE_CREATIVE,
            json_schema=BulletRewriteResult,
            timeout=settings.STRUCTURE_TIMEOUT,
        )
        bundle.report.rewrites = rewrites.rewrites
        detail = f"{len(rewrites.rewrites)} bullets rewritten"
    else:
        detail = "no experience bullets found to rewrite"
    yield ReviewEvent("rewrites", "done", 3, total, detail=detail)

    # -- Stage 4: keyword gap (C4, analysis -> low temp) -------------------- #
    yield ReviewEvent("keyword_gap", "running", 4, total)
    gap_prompt = render_prompt(
        "keyword_gap", jd_chunks=bundle.jd_context, resume_chunks=bundle.resume_context
    )
    gaps: KeywordGapResult = await client.chat(
        [{"role": "user", "content": gap_prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=KeywordGapResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    bundle.report.gaps = gaps.gaps
    missing = sum(1 for gap in gaps.gaps if not gap.present_in_resume)
    yield ReviewEvent("keyword_gap", "done", 4, total, detail=f"{missing} missing keywords")

    # -- Stage 5: ATS checklist (deterministic, instant) -------------------- #
    yield ReviewEvent("ats", "running", 5, total)
    bundle.report.ats = run_ats_checks(resume.raw_text, parsed)
    yield ReviewEvent(
        "ats",
        "done",
        5,
        total,
        detail=f"{bundle.report.ats.passed_count}/{bundle.report.ats.total} checks passed",
    )

    yield ReviewEvent("complete", "done", total, total, report=bundle.report)
    logger.info("Review complete for resume=%d jd=%d", resume.id, jd.id)
