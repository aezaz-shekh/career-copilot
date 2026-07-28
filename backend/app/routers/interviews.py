"""Interview prep endpoints (Phase 2).

Step 2.1: generate a question bank from a resume + JD. This is one large LLM call
that stays silent for a couple of minutes on CPU. A plain POST behind the Vite
dev proxy looks frozen (and a silent connection can be severed mid-flight), so
the endpoint streams progress as Server-Sent Events — a heartbeat carrying
elapsed time every few seconds, then a `done` event with the questions. Mirrors
`/api/review`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.llm.client import OllamaError
from app.models import InterviewSession, InterviewTurn, JobDescription, ResumeVersion
from app.models.base import InterviewMode, utcnow
from app.schemas.interview import (
    AnswerFeedback,
    AnswerRequest,
    AnswerResponse,
    AnswerScores,
    QuestionBankRequest,
    SessionListItem,
    SessionRead,
    StartInterviewRequest,
    StartInterviewResponse,
    TurnRead,
)
from app.services import interview_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])

# How often to emit a heartbeat while the one long generation runs, so the
# connection never goes silent and the UI can show elapsed time.
HEARTBEAT_SECONDS = 2.5


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _turn_to_read(turn: InterviewTurn, *, reveal_scores: bool) -> TurnRead:
    """Convert a stored turn to its API shape, hiding scores mid-interview."""
    meta = turn.scores_json or {}
    scores = None
    feedback = None
    if reveal_scores and isinstance(meta.get("scores"), dict):
        scores = AnswerScores(**meta["scores"])
        if isinstance(meta.get("feedback"), dict):
            feedback = AnswerFeedback(**meta["feedback"])
    return TurnRead(
        id=turn.id,
        question=turn.question,
        answer=turn.answer,
        is_followup=bool(meta.get("is_followup")),
        scores=scores,
        feedback=feedback,
        improvement_tip=meta.get("improvement_tip") if reveal_scores else None,
        created_at=turn.created_at,
    )


@router.post("/questions", summary="Generate a question bank, streaming progress (SSE)")
async def generate_questions(
    request: QuestionBankRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Generate an interview question bank grounded in the resume and JD.

    Validates the ids up front (clean 404), then streams the generation as SSE:

      event: step       {stage, detail}       -- retrieval, then generation
      event: heartbeat  {elapsed_s}           -- every few seconds while it runs
      event: error      {message, hint}       -- on failure
      event: done       {questions, behavioral_count, technical_count, elapsed_ms}

    The heartbeats keep the (otherwise silent) connection alive so it can't be
    severed mid-generation, and give the UI a live elapsed-time to show.
    """
    # Topic mode: a chosen job title (and optional focus topics), no resume/JD.
    topic_mode = bool((request.job_title or "").strip() or (request.topics or "").strip())
    if not topic_mode:
        if session.get(ResumeVersion, request.resume_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Pick a job to generate questions for.",
                    "hint": "Choose a job from the list (or type your topics).",
                },
            )
        if session.get(JobDescription, request.jd_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": f"No job description with id {request.jd_id}",
                    "hint": "Save a job description first.",
                },
            )

    # Bind the stream's own session to the same engine as the request session, so
    # a test's overridden database is honoured (the request-scoped session is torn
    # down once headers are sent). Same pattern as /api/review.
    engine = session.get_bind()

    async def event_stream() -> AsyncIterator[str]:
        with Session(engine) as stream_session:
            resume_row = (
                None if topic_mode else stream_session.get(ResumeVersion, request.resume_id)
            )
            jd_row = None if topic_mode else stream_session.get(JobDescription, request.jd_id)
            try:
                yield _sse(
                    "step",
                    {
                        "stage": "retrieving",
                        "detail": "Preparing your topics…"
                        if topic_mode
                        else "Finding the most relevant resume and JD sections…",
                    },
                )

                # Run the (long) generation as a task so we can emit heartbeats
                # while it works. The heartbeat loop only sleeps and yields — it
                # never touches the session — so there is no concurrent DB use.
                task = asyncio.create_task(
                    interview_service.generate_question_bank(
                        stream_session,
                        resume_row,
                        jd_row,
                        job_title=request.job_title,
                        topics=request.topics,
                        n_behavioral=request.n_behavioral,
                        n_technical=request.n_technical,
                    )
                )
                yield _sse(
                    "step",
                    {
                        "stage": "generating",
                        "detail": "Writing questions with the local model…",
                    },
                )

                started = time.monotonic()
                last_beat = started
                while not task.done():
                    # Poll often so completion is detected promptly, but only emit
                    # a heartbeat every HEARTBEAT_SECONDS.
                    await asyncio.sleep(0.2)
                    if task.done():
                        break
                    now = time.monotonic()
                    if now - last_beat >= HEARTBEAT_SECONDS:
                        last_beat = now
                        yield _sse("heartbeat", {"elapsed_s": int(now - started)})

                result, elapsed_ms = await task  # re-raises any generation error

                yield _sse(
                    "done",
                    {
                        "questions": [q.model_dump() for q in result.questions],
                        "behavioral_count": sum(
                            1 for q in result.questions if q.type == "behavioral"
                        ),
                        "technical_count": sum(
                            1 for q in result.questions if q.type == "technical"
                        ),
                        "elapsed_ms": elapsed_ms,
                    },
                )
            except OllamaError as exc:
                logger.warning("Question generation failed: %s", exc.message)
                yield _sse("error", {"message": exc.message, "hint": exc.hint})
            except Exception as exc:  # noqa: BLE001 - stream must not 500 mid-body
                logger.exception("Unexpected question-generation failure")
                yield _sse(
                    "error",
                    {
                        "message": f"Question generation failed: {exc}",
                        "hint": "Check the backend logs and retry.",
                    },
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------- #
# Mock interview flow (Phase 2.2)
# --------------------------------------------------------------------------- #


@router.post("/start", response_model=StartInterviewResponse, summary="Start a mock interview")
def start_interview(
    request: StartInterviewRequest, session: Session = Depends(get_session)
) -> StartInterviewResponse:
    """Create an interview session from a set of chosen questions.

    Takes the question objects (not ids): the Phase 2.1 bank is ephemeral, so
    the frontend sends the selected questions and they are stored on the session
    for replay and resume.
    """
    if request.jd_id is not None and session.get(JobDescription, request.jd_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No job description with id {request.jd_id}",
                "hint": "Pick a saved JD.",
            },
        )

    interview = InterviewSession(
        jd_id=request.jd_id,
        mode=InterviewMode(request.mode),
        question_bank_json=[q.model_dump() for q in request.questions],
    )
    session.add(interview)
    session.commit()
    session.refresh(interview)
    logger.info("Started interview id=%d with %d questions", interview.id, len(request.questions))

    return StartInterviewResponse(
        session_id=interview.id, mode=interview.mode.value, questions=request.questions
    )


@router.post("/answer", response_model=AnswerResponse, summary="Submit and score one answer")
async def submit_answer(
    request: AnswerRequest, session: Session = Depends(get_session)
) -> AnswerResponse:
    """Score an answer (two LLM calls) and store the turn.

    Scores are stored but not returned — the UI reveals them only when the
    session ends, which is closer to a real interview.
    """
    interview = session.get(InterviewSession, request.session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No interview session {request.session_id}",
                "hint": "Start one first.",
            },
        )

    jd_context = ""
    if interview.jd_id is not None:
        jd = session.get(JobDescription, interview.jd_id)
        if jd is not None:
            jd_context = jd.raw_text[:2500]

    try:
        scoring, followup = await interview_service.score_answer(
            request.question, request.answer, jd_context
        )
    except OllamaError as exc:
        logger.warning("Answer scoring failed: %s", exc.message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc

    turn = InterviewTurn(
        session_id=interview.id,
        question=request.question,
        answer=request.answer,
        mode=interview.mode,
        scores_json={
            "scores": scoring.scores.model_dump(),
            "feedback": scoring.feedback.model_dump(),
            "improvement_tip": scoring.improvement_tip,
            "is_followup": request.is_followup,
            "followup_question": followup.followup_question if followup.needs_followup else None,
        },
        feedback=scoring.improvement_tip,
    )
    session.add(turn)
    session.commit()
    session.refresh(turn)

    return AnswerResponse(
        turn_id=turn.id,
        needs_followup=followup.needs_followup,
        followup_question=followup.followup_question if followup.needs_followup else None,
    )


@router.post("/{session_id}/finish", response_model=SessionRead, summary="End a session")
def finish_interview(session_id: int, session: Session = Depends(get_session)) -> SessionRead:
    """Mark the session finished and return the full replay with scores revealed."""
    interview = session.get(InterviewSession, session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No interview session {session_id}",
                "hint": "It may have been deleted.",
            },
        )
    if interview.ended_at is None:
        interview.ended_at = utcnow()
        session.commit()
        session.refresh(interview)
    return _session_to_read(interview, reveal_scores=True)


@router.get("", response_model=list[SessionListItem], summary="List interview sessions")
def list_interviews(session: Session = Depends(get_session)) -> list[SessionListItem]:
    interviews = session.query(InterviewSession).order_by(InterviewSession.started_at.desc()).all()
    return [
        SessionListItem(
            id=iv.id,
            jd_id=iv.jd_id,
            mode=iv.mode.value,
            started_at=iv.started_at,
            ended_at=iv.ended_at,
            turn_count=len(iv.turns),
        )
        for iv in interviews
    ]


@router.get("/{session_id}", response_model=SessionRead, summary="Replay a session")
def get_interview(session_id: int, session: Session = Depends(get_session)) -> SessionRead:
    """Full replay of a session. Scores are revealed once the session has ended."""
    interview = session.get(InterviewSession, session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No interview session {session_id}",
                "hint": "It may have been deleted.",
            },
        )
    return _session_to_read(interview, reveal_scores=interview.ended_at is not None)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a session")
def delete_interview(session_id: int, session: Session = Depends(get_session)) -> None:
    interview = session.get(InterviewSession, session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No interview session {session_id}", "hint": "Nothing to delete."},
        )
    session.delete(interview)
    session.commit()


def _session_to_read(interview: InterviewSession, *, reveal_scores: bool) -> SessionRead:
    turns = [_turn_to_read(t, reveal_scores=reveal_scores) for t in interview.turns]
    summary = (
        interview_service.summarize_session(interview.turns) if reveal_scores and turns else None
    )
    return SessionRead(
        id=interview.id,
        jd_id=interview.jd_id,
        mode=interview.mode.value,
        started_at=interview.started_at,
        ended_at=interview.ended_at,
        turns=turns,
        summary=summary,
    )
