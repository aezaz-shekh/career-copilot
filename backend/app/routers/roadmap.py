"""Career roadmap endpoints (Phase 3, Prompt 3.1).

`POST /api/roadmap` runs the two-call skill-gap + roadmap pipeline and streams
progress as Server-Sent Events — on CPU-only hardware the two 3B generations take
minutes, and a plain POST behind the Vite proxy would look frozen (and a silent
connection can be severed mid-flight). Mirrors `/api/review`.

The plan and its editable action rows are persisted before the `done` event, so
`plan_id` always refers to something the GET/PATCH endpoints can load — which is
what SOW module 4 requires: "generated, saved, reopened, and updated across app
restarts".
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
from app.models import ResumeVersion, RoadmapItem, RoadmapPlan
from app.schemas.roadmap import (
    RoadmapItemUpdate,
    RoadmapRead,
    RoadmapRequest,
    RoadmapSummary,
)
from app.services import roadmap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/roadmap", tags=["roadmap"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("", summary="Generate a career roadmap, streaming progress (SSE)")
async def create_roadmap(
    request: RoadmapRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Validate inputs up front, then stream the roadmap as it is generated."""
    resume = session.get(ResumeVersion, request.resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No resume with id {request.resume_id}",
                "hint": "Save a resume first.",
            },
        )
    if (
        request.regenerate_plan_id is not None
        and session.get(RoadmapPlan, request.regenerate_plan_id) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No roadmap with id {request.regenerate_plan_id} to regenerate",
                "hint": "Generate a fresh roadmap instead.",
            },
        )

    # Bind the stream's session to the same engine as the request session so a
    # test's overridden database is honoured (the request session is gone once
    # headers are sent). Same pattern as /api/review.
    engine = session.get_bind()

    async def event_stream() -> AsyncIterator[str]:
        with Session(engine) as stream_session:
            resume_row = stream_session.get(ResumeVersion, request.resume_id)
            try:
                skill_gap = None
                roadmap = None
                async for ev in roadmap_service.generate_roadmap(
                    stream_session, resume_row, request.target_role
                ):
                    if ev.stage == "complete":
                        skill_gap = ev.skill_gap
                        roadmap = ev.roadmap
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

                plan = roadmap_service.persist_plan(
                    stream_session,
                    target_role=request.target_role,
                    current_profile=(resume_row.raw_text or "")[:500] or None,
                    skill_gap=skill_gap,
                    roadmap=roadmap,
                    regenerate_plan_id=request.regenerate_plan_id,
                )
                read = roadmap_service.assemble_read(plan)
                yield _sse("done", {"plan_id": plan.id, "roadmap": read.model_dump(mode="json")})
            except OllamaError as exc:
                logger.warning("Roadmap generation failed: %s", exc.message)
                yield _sse("error", {"message": exc.message, "hint": exc.hint})
            except Exception as exc:  # noqa: BLE001 - stream must not 500 mid-body
                logger.exception("Unexpected roadmap failure")
                yield _sse(
                    "error",
                    {
                        "message": f"Roadmap generation failed: {exc}",
                        "hint": "Check the backend logs and retry.",
                    },
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[RoadmapSummary], summary="List saved roadmaps")
def list_roadmaps(session: Session = Depends(get_session)) -> list[RoadmapSummary]:
    plans = session.query(RoadmapPlan).order_by(RoadmapPlan.updated_at.desc()).all()
    return [
        RoadmapSummary(
            id=plan.id,
            target_role=plan.target_role,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            done_count=sum(1 for it in plan.items if it.is_done),
            total_count=len(plan.items),
        )
        for plan in plans
    ]


@router.get("/{plan_id}", response_model=RoadmapRead, summary="Open a saved roadmap")
def get_roadmap(plan_id: int, session: Session = Depends(get_session)) -> RoadmapRead:
    plan = session.get(RoadmapPlan, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No roadmap with id {plan_id}",
                "hint": "It may have been deleted.",
            },
        )
    return roadmap_service.assemble_read(plan)


@router.patch("/items/{item_id}", summary="Tick or untick one roadmap action")
def update_item(
    item_id: int, update: RoadmapItemUpdate, session: Session = Depends(get_session)
) -> dict:
    """Toggle an action's done state — one row update, persisted immediately."""
    item = session.get(RoadmapItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No roadmap action with id {item_id}", "hint": "Reopen the plan."},
        )
    item.is_done = update.done
    session.commit()
    return {"item_id": item_id, "done": item.is_done}


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a roadmap")
def delete_roadmap(plan_id: int, session: Session = Depends(get_session)) -> None:
    plan = session.get(RoadmapPlan, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No roadmap with id {plan_id}", "hint": "Nothing to delete."},
        )
    session.delete(plan)
    session.commit()
