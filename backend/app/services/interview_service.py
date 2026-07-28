"""Interview question-bank generation (Phase 2, Prompt 2.1).

One LLM call, grounded in the candidate's resume and the job's requirements so
the questions are specific rather than generic. Short resumes/JDs (the common
case) are fed whole, skipping embedding so only the chat model loads; longer docs
fall back to RAG retrieval (embedding model, then one swap to the chat model).
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import rag
from app.llm.client import OllamaClient
from app.llm.prompts import render_prompt
from app.models import JobDescription, ResumeVersion
from app.models.base import SourceType
from app.schemas.interview import (
    RUBRIC_DIMENSIONS,
    FollowupResult,
    QuestionBankResult,
    ScoringResult,
    SessionSummary,
)

logger = logging.getLogger(__name__)

RETRIEVE_TOP_K = 6
# A resume/JD this short already fits whole in the prompt, so RAG retrieval would
# only add two embedding calls and an embed->chat model swap (expensive on 8 GB
# RAM) for no extra grounding. Below this size we feed the raw text directly and
# keep the chat model as the only model that has to load.
SKIP_RETRIEVAL_CHARS = 3500

_DIMENSION_LABEL = {
    "structure": "Structure",
    "specificity": "Specificity",
    "star_adherence": "STAR method",
    "relevance": "Relevance",
}
STRONG = 3.5  # dimension average at or above this reads as a strength


def _enforce_counts(
    result: QuestionBankResult, n_behavioral: int, n_technical: int
) -> QuestionBankResult:
    """Keep the first n of each type, preserving order.

    Behavioral and technical questions are interleaved in the model's output, so
    filtering by type before truncating keeps both kinds even when the model
    front-loads one type.
    """
    behavioral = [q for q in result.questions if q.type == "behavioral"][:n_behavioral]
    technical = [q for q in result.questions if q.type == "technical"][:n_technical]
    return QuestionBankResult(questions=behavioral + technical)


async def generate_question_bank(
    session: Session,
    resume: ResumeVersion | None = None,
    jd: JobDescription | None = None,
    *,
    job_title: str | None = None,
    topics: str | None = None,
    n_behavioral: int = 6,
    n_technical: int = 6,
    client: OllamaClient | None = None,
) -> tuple[QuestionBankResult, int]:
    """Generate a bank of behavioral and technical questions.

    Two modes:
      * resume + JD  → questions grounded (via RAG) in the candidate's own resume.
      * job_title (+ optional focus topics) → questions general to a chosen role,
        no resume needed. This backs the quick "pick a job, type topics" flow.

    Returns the validated questions and the generation time in milliseconds.
    """
    settings = get_settings()
    client = client or OllamaClient()

    # -- Context ------------------------------------------------------------ #
    if resume is not None and jd is not None:
        if (
            len(resume.raw_text) <= SKIP_RETRIEVAL_CHARS
            and len(jd.raw_text) <= SKIP_RETRIEVAL_CHARS
        ):
            # Whole document fits — skip embedding entirely so the only model that
            # loads is the chat model (no embed->chat swap on the 8 GB machine).
            resume_context = resume.raw_text
            jd_context = jd.raw_text
        else:
            # Retrieval (embedding model resident, then one swap to the chat model).
            query = f"{jd.title}\n{jd.raw_text}"[:4000]
            resume_hits = await rag.retrieve(
                session,
                query,
                source_ids={SourceType.RESUME: resume.id},
                top_k=RETRIEVE_TOP_K,
                client=client,
            )
            jd_hits = await rag.retrieve(
                session,
                query,
                source_ids={SourceType.JD: jd.id},
                top_k=RETRIEVE_TOP_K,
                client=client,
            )
            resume_context = rag.build_context_block(resume_hits) or resume.raw_text[:3000]
            jd_context = rag.build_context_block(jd_hits) or jd.raw_text[:3000]
    else:
        # Topic mode: build the context from a chosen job title and focus topics.
        resume_context = "(No resume provided — write questions general to the role.)"
        role = (job_title or "the role").strip() or "the role"
        jd_context = f"Target role: {role}."
        focus = (topics or "").strip()
        if focus:
            jd_context += f"\nFocus the questions specifically on these topics: {focus}"

    # -- Generation (chat model resident) ----------------------------------- #
    prompt = render_prompt(
        "question_gen",
        n_behavioral=n_behavioral,
        n_technical=n_technical,
        jd_chunks=jd_context,
        resume_chunks=resume_context,
    )

    started = time.perf_counter()
    result: QuestionBankResult = await client.chat(
        [{"role": "user", "content": prompt}],
        # A small, fast model: a full bank on the 3B model takes minutes on an
        # 8 GB CPU box, and these grounded, templated questions are well within a
        # 1B model's reach. Scoring keeps the higher-quality CHAT_MODEL.
        model=settings.QUESTION_MODEL,
        # Question wording benefits from variety; grounding comes from the
        # context above, not from a cold temperature.
        temperature=settings.TEMPERATURE_CREATIVE,
        json_schema=QuestionBankResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # The 3B model does not reliably honour "exactly N of each" — a real run
    # asked for 6+6 and got 7+8. The over-generation is useful (a bigger pool),
    # so we keep the first N of each type rather than discarding the request's
    # contract. This makes the returned counts match what was asked for.
    result = _enforce_counts(result, n_behavioral, n_technical)

    behavioral = sum(1 for q in result.questions if q.type == "behavioral")
    technical = sum(1 for q in result.questions if q.type == "technical")
    logger.info(
        "Generated %d questions (%d behavioral, %d technical) in %d ms",
        len(result.questions),
        behavioral,
        technical,
        elapsed_ms,
    )
    return result, elapsed_ms


# --------------------------------------------------------------------------- #
# Answer scoring + follow-up (Phase 2.2)
# --------------------------------------------------------------------------- #


async def score_answer(
    question: str,
    answer: str,
    jd_context: str,
    *,
    client: OllamaClient | None = None,
) -> tuple[ScoringResult, FollowupResult]:
    """Score one answer and decide on a follow-up — two chat calls, no retrieval.

    Scoring runs at temperature 0.2 so the same answer scores consistently
    (SOW Section 12: within +/-1 point on repeats). Both calls use the chat
    model back to back, so there is no embedding-model swap per answer.

    `jd_context` is the JD's own text (not a RAG retrieval): the question already
    encodes the requirement, so a per-answer embedding call would only add a slow
    model swap for no gain.
    """
    settings = get_settings()
    client = client or OllamaClient()

    scoring_prompt = render_prompt(
        "answer_scoring", question=question, jd_chunks=jd_context, answer=answer
    )
    scoring: ScoringResult = await client.chat(
        [{"role": "user", "content": scoring_prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=ScoringResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )

    followup_prompt = render_prompt("followup_decider", question=question, answer=answer)
    followup: FollowupResult = await client.chat(
        [{"role": "user", "content": followup_prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=FollowupResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    # Guard the model against saying "yes" but giving no question.
    if followup.needs_followup and not (followup.followup_question or "").strip():
        followup.needs_followup = False

    return scoring, followup


def summarize_session(turns: list) -> SessionSummary:
    """Compute a session summary deterministically from the stored turns.

    Deterministic on purpose: averaging stored scores is exact and repeatable,
    where a summarising LLM call would be slow and could contradict the numbers
    it is meant to summarise.
    """
    scored = [
        t.scores_json
        for t in turns
        if t.scores_json and isinstance(t.scores_json.get("scores"), dict)
    ]

    averages: dict[str, float] = {}
    for dim in RUBRIC_DIMENSIONS:
        values = [s["scores"][dim] for s in scored if dim in s["scores"]]
        averages[dim] = round(sum(values) / len(values), 2) if values else 0.0

    overall = round(sum(averages.values()) / len(RUBRIC_DIMENSIONS), 2) if scored else 0.0

    ranked = sorted(RUBRIC_DIMENSIONS, key=lambda d: averages[d], reverse=True)
    strengths = [
        f"{_DIMENSION_LABEL[d]} — averaging {averages[d]}/5"
        for d in ranked
        if averages[d] >= STRONG
    ][:3]
    improvement_areas = [
        f"{_DIMENSION_LABEL[d]} — averaging {averages[d]}/5"
        for d in reversed(ranked)
        if averages[d] < STRONG
    ][:3]

    tips = [s["improvement_tip"] for s in scored if s.get("improvement_tip")][:3]

    return SessionSummary(
        answered=len(scored),
        averages=averages,
        overall_average=overall,
        strengths=strengths,
        improvement_areas=improvement_areas,
        tips=tips,
    )
