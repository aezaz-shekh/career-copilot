"""Resume ingestion, structuring, and storage.

The flow is three deliberate steps rather than one upload-and-done call:

    upload  ->  structure  ->  review and edit  ->  save

SOW Section 11 makes the review step mandatory: PDF layout varies enormously and
a 3B model is not infallible, so nothing is persisted or fed downstream until
the user has seen it. `upload` and `structure` therefore write nothing to disk.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.llm.client import OllamaError
from app.models import ResumeVersion
from app.models.base import SourceType
from app.schemas.resume import (
    ExtractionQuality,
    ResumeCreate,
    ResumeRead,
    ResumeSummary,
    StructureRequest,
    StructureResponse,
    UploadResponse,
)
from app.services import resume_service
from app.services.indexing import index_document
from app.services.pdf_parser import ResumeParseError, extract_text
from app.services.vector_store import delete_for_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/upload", response_model=UploadResponse, summary="Extract text from a PDF or TXT")
async def upload_resume(file: UploadFile = File(...)) -> UploadResponse:
    """Extract raw text from an uploaded resume. Nothing is saved yet.

    The response carries a quality verdict alongside the text, so the UI can warn
    the user when extraction looks unreliable instead of letting them discover it
    three screens later.
    """
    settings = get_settings()
    data = await file.read()

    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "message": f"File is larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                "hint": "Resumes are usually well under 1 MB. Check you picked the right file.",
            },
        )

    try:
        result = extract_text(data, file.filename or "upload")
    except ResumeParseError as exc:
        logger.info("Rejected upload %r: %s", file.filename, exc.message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc

    return UploadResponse(
        raw_text=result.text,
        filename=file.filename or "upload",
        quality=ExtractionQuality(
            is_usable=result.quality.is_usable,
            parser_used=result.parser_used,
            fallback_used=result.fallback_used,
            character_count=result.quality.character_count,
            page_count=result.quality.page_count,
            warnings=result.quality.warnings,
        ),
    )


@router.post("/structure", response_model=StructureResponse, summary="Split text into sections")
async def structure_resume(request: StructureRequest) -> StructureResponse:
    """Turn raw resume text into structured sections using the local model.

    Slow on CPU-only hardware — a full resume can take minutes — so the elapsed
    time comes back with the result and the UI shows it.
    """
    try:
        parsed, elapsed_ms = await resume_service.structure_resume(request.raw_text)
    except OllamaError as exc:
        logger.warning("Resume structuring failed: %s", exc.message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc

    return StructureResponse(parsed=parsed, elapsed_ms=elapsed_ms)


@router.post(
    "", response_model=ResumeRead, status_code=status.HTTP_201_CREATED, summary="Save a version"
)
async def create_resume(
    payload: ResumeCreate, session: Session = Depends(get_session)
) -> ResumeVersion:
    """Persist a resume version the user has reviewed, then index it for RAG.

    Versions accumulate rather than overwrite, so a tailored resume can be
    compared against the original (SOW Section 4.1, module 1).

    Indexing runs here, once, at save time — this is the batch-embed step that
    keeps the chat model from being evicted during later generation on 8 GB RAM.
    A failed index never fails the save; the document is stored regardless.
    """
    resume = ResumeVersion(
        title=payload.title,
        raw_text=payload.raw_text,
        parsed_json=payload.parsed_json.model_dump() if payload.parsed_json else None,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    logger.info("Saved resume version id=%d %r", resume.id, resume.title)

    chunks = await index_document(session, SourceType.RESUME, resume.id, resume.raw_text)
    logger.info("Indexed resume id=%d into %d chunks", resume.id, chunks)
    return resume


@router.get("", response_model=list[ResumeSummary], summary="List saved versions")
def list_resumes(session: Session = Depends(get_session)) -> list[ResumeVersion]:
    return session.query(ResumeVersion).order_by(ResumeVersion.created_at.desc()).all()


@router.get("/{resume_id}", response_model=ResumeRead, summary="Fetch one version")
def get_resume(resume_id: int, session: Session = Depends(get_session)) -> ResumeVersion:
    resume = session.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No resume with id {resume_id}",
                "hint": "It may have been deleted.",
            },
        )
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a version")
def delete_resume(resume_id: int, session: Session = Depends(get_session)) -> None:
    resume = session.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No resume with id {resume_id}", "hint": "Nothing to delete."},
        )
    # Chunks reference the resume polymorphically (no FK), so remove them explicitly.
    delete_for_source(session, SourceType.RESUME, resume_id)
    session.delete(resume)
    session.commit()
