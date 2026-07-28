"""Cross-feature dashboard stats (Phase 4, Prompt 4.1).

One read that the home dashboard renders: latest resume, interview score trend,
roadmap completion, and outreach reply rate — so the user sees their progress
across every module at a glance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import (
    Contact,
    InterviewSession,
    OutreachDraft,
    ResumeVersion,
    RoadmapItem,
    RoadmapPlan,
)
from app.services import interview_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", summary="Dashboard summary across all modules")
def dashboard_stats(session: Session = Depends(get_session)) -> dict:
    # -- Resume --------------------------------------------------------------
    resumes = session.query(ResumeVersion).order_by(ResumeVersion.created_at.desc()).all()
    resume_block = None
    if resumes:
        latest = resumes[0]
        resume_block = {
            "count": len(resumes),
            "latest_title": latest.title,
            "latest_at": latest.created_at.isoformat(),
        }

    # -- Interviews: score trend over finished sessions ----------------------
    finished = [
        iv
        for iv in session.query(InterviewSession).order_by(InterviewSession.started_at).all()
        if iv.ended_at is not None
    ]
    trend = [
        interview_service.summarize_session(iv.turns).overall_average for iv in finished if iv.turns
    ]
    interviews_block = {
        "count": len(finished),
        "score_trend": trend,
        "latest_average": trend[-1] if trend else None,
    }

    # -- Roadmap completion --------------------------------------------------
    items = session.query(RoadmapItem).all()
    done = sum(1 for it in items if it.is_done)
    total = len(items)
    roadmap_block = {
        "plans": session.query(RoadmapPlan).count(),
        "done": done,
        "total": total,
        "percent": round(done / total * 100) if total else 0,
    }

    # -- Outreach reply rate -------------------------------------------------
    drafts = session.query(OutreachDraft).all()
    sent = sum(1 for d in drafts if d.status.value in ("sent", "replied"))
    replied = sum(1 for d in drafts if d.status.value == "replied")
    outreach_block = {
        "contacts": session.query(Contact).count(),
        "drafts": len(drafts),
        "sent": sent,
        "replied": replied,
        "reply_rate": round(replied / sent * 100) if sent else 0,
    }

    return {
        "resume": resume_block,
        "interviews": interviews_block,
        "roadmap": roadmap_block,
        "outreach": outreach_block,
    }
