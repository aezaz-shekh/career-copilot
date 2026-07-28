"""Job description storage.

Paste-only by design. SOW Section 4.2 rules out scraping LinkedIn, Indeed or
Naukri on Terms-of-Service grounds, so there is no fetch-by-URL endpoint here
and there will not be one.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import JobDescription
from app.models.base import SourceType
from app.schemas.resume import (
    JobDescriptionCreate,
    JobDescriptionRead,
    JobDescriptionSummary,
)
from app.services.indexing import index_document
from app.services.vector_store import delete_for_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jds", tags=["job descriptions"])


@router.post(
    "", response_model=JobDescriptionRead, status_code=status.HTTP_201_CREATED, summary="Save a JD"
)
async def create_jd(
    payload: JobDescriptionCreate, session: Session = Depends(get_session)
) -> JobDescription:
    """Save a pasted job description exactly as provided, then index it for RAG.

    Stored verbatim rather than summarised, because keyword-gap analysis needs
    the employer's own wording to match against. Indexing is best-effort and
    never blocks the save.
    """
    jd = JobDescription(title=payload.title, company=payload.company, raw_text=payload.raw_text)
    session.add(jd)
    session.commit()
    session.refresh(jd)
    logger.info("Saved job description id=%d %r", jd.id, jd.title)

    chunks = await index_document(session, SourceType.JD, jd.id, jd.raw_text)
    logger.info("Indexed job description id=%d into %d chunks", jd.id, chunks)
    return jd


@router.get("", response_model=list[JobDescriptionSummary], summary="List saved JDs")
def list_jds(session: Session = Depends(get_session)) -> list[JobDescription]:
    return session.query(JobDescription).order_by(JobDescription.created_at.desc()).all()


@router.get("/{jd_id}", response_model=JobDescriptionRead, summary="Fetch one JD")
def get_jd(jd_id: int, session: Session = Depends(get_session)) -> JobDescription:
    jd = session.get(JobDescription, jd_id)
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No job description with id {jd_id}",
                "hint": "It may have been deleted.",
            },
        )
    return jd


@router.delete("/{jd_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a JD")
def delete_jd(jd_id: int, session: Session = Depends(get_session)) -> None:
    jd = session.get(JobDescription, jd_id)
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No job description with id {jd_id}", "hint": "Nothing to delete."},
        )
    # Chunks reference the JD polymorphically (no FK), so remove them explicitly.
    delete_for_source(session, SourceType.JD, jd_id)
    session.delete(jd)
    session.commit()
