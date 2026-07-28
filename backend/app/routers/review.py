"""Resume review — the headline Phase 1 feature (Prompt 1.3).

`POST /api/review` runs the four-stage review and streams progress as Server-Sent
Events, because on CPU-only hardware the three LLM stages take minutes and a
frozen screen would look broken. The stream emits:

  event: step   {stage, status, index, total, detail}   -- one before & after each stage
  event: error  {message, hint}                          -- on failure
  event: done   {report_id, report}                      -- final, with the stored report

The report is persisted before the `done` event fires, so `report_id` always
refers to something the GET endpoints can load.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.llm.client import OllamaError
from app.models import JobDescription, ResumeVersion, ReviewReport
from app.schemas.review import ReviewRead, ReviewRequest, ReviewSummary
from app.services import review_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("", summary="Run a resume review, streaming progress (SSE)")
async def run_review(
    request: ReviewRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Validate the inputs, then stream the review as it runs.

    Validation happens up front against the request-scoped session so a bad id
    returns a clean 404. The long-running stream then uses its own session,
    because the request-scoped one is torn down once headers are sent.
    """
    resume = session.get(ResumeVersion, request.resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No resume with id {request.resume_id}",
                "hint": "Save a resume first.",
            },
        )
    jd = session.get(JobDescription, request.jd_id)
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No job description with id {request.jd_id}",
                "hint": "Save a job description first.",
            },
        )

    # Bind the stream's own session to the SAME engine as the request session,
    # so a test's overridden database (or any future multi-engine setup) is
    # honoured rather than silently falling back to the default engine.
    engine = session.get_bind()

    async def event_stream() -> AsyncIterator[str]:
        # A dedicated session for the life of the stream — retrieval needs it,
        # and the request-scoped session is already gone by now.
        with Session(engine) as stream_session:
            resume_row = stream_session.get(ResumeVersion, request.resume_id)
            jd_row = stream_session.get(JobDescription, request.jd_id)
            try:
                report = None
                async for ev in review_service.generate_review(stream_session, resume_row, jd_row):
                    if ev.stage == "complete" and ev.report is not None:
                        report = ev.report
                        break
                    yield _sse(
                        "step",
                        {
                            "stage": ev.stage,
                            "status": ev.status,
                            "index": ev.index,
                            "total": ev.total,
                            "detail": ev.detail,
                        },
                    )

                stored = ReviewReport(
                    resume_id=request.resume_id,
                    jd_id=request.jd_id,
                    report_json=report.model_dump(),
                )
                stream_session.add(stored)
                stream_session.commit()
                stream_session.refresh(stored)

                yield _sse(
                    "done",
                    {"report_id": stored.id, "report": report.model_dump()},
                )
            except OllamaError as exc:
                logger.warning("Review failed: %s", exc.message)
                yield _sse("error", {"message": exc.message, "hint": exc.hint})
            except Exception as exc:  # noqa: BLE001 - stream must not 500 mid-body
                logger.exception("Unexpected review failure")
                yield _sse(
                    "error",
                    {
                        "message": f"Review failed: {exc}",
                        "hint": "Check the backend logs and retry.",
                    },
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[ReviewSummary], summary="List stored reviews")
def list_reviews(session: Session = Depends(get_session)) -> list[ReviewReport]:
    return session.query(ReviewReport).order_by(ReviewReport.created_at.desc()).all()


@router.get("/{review_id}", response_model=ReviewRead, summary="Fetch a stored review")
def get_review(review_id: int, session: Session = Depends(get_session)) -> ReviewReport:
    review = session.get(ReviewReport, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No review with id {review_id}",
                "hint": "It may have been deleted.",
            },
        )
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a review")
def delete_review(review_id: int, session: Session = Depends(get_session)) -> None:
    review = session.get(ReviewReport, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No review with id {review_id}", "hint": "Nothing to delete."},
        )
    session.delete(review)
    session.commit()
