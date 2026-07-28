"""SQLAlchemy ORM models.

Importing every model here is what registers it on `Base.metadata`, so
`init_db()` can create the full schema in one call.
"""

from app.models.base import (
    Base,
    InterviewMode,
    OutreachPlatform,
    OutreachStatus,
    RoadmapHorizon,
    SourceType,
    utcnow,
)
from app.models.embedding import EmbeddingChunk
from app.models.interview import InterviewSession, InterviewTurn
from app.models.outreach import Contact, OutreachDraft
from app.models.resume import JobDescription, ResumeVersion
from app.models.review import ReviewReport
from app.models.roadmap import RoadmapItem, RoadmapPlan

__all__ = [
    "Base",
    "Contact",
    "EmbeddingChunk",
    "InterviewMode",
    "InterviewSession",
    "InterviewTurn",
    "JobDescription",
    "OutreachDraft",
    "OutreachPlatform",
    "OutreachStatus",
    "ResumeVersion",
    "ReviewReport",
    "RoadmapHorizon",
    "RoadmapItem",
    "RoadmapPlan",
    "SourceType",
    "utcnow",
]
