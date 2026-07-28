"""Networking / outreach endpoints (Phase 3a, Prompt 3a.1).

Contacts are typed by hand (no scraping, SOW 4.2). `POST /api/outreach/draft`
generates three toned variants grounded in the sender's resume and target role,
streaming progress as Server-Sent Events with a heartbeat — the one 3B
generation (plus any length-fix regeneration) takes a minute or two on CPU, and
a silent POST behind the Vite proxy would look frozen. The app never sends
anything; the user copies a draft and marks it sent / replied afterwards.
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
from app.models import Contact, OutreachDraft, ResumeVersion, RoadmapPlan
from app.models.base import OutreachPlatform, OutreachStatus
from app.schemas.outreach import (
    PLATFORM_CHAR_LIMITS,
    ContactCreate,
    ContactRead,
    ContactSummary,
    ContactUpdate,
    DraftRead,
    DraftRequest,
    DraftStatusUpdate,
)
from app.services import outreach_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

# How often to emit a heartbeat while the generation runs (keeps the SSE
# connection alive so the proxy never severs it and the UI shows elapsed time).
HEARTBEAT_SECONDS = 2.5


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _draft_to_read(draft: OutreachDraft) -> DraftRead:
    platform = draft.platform.value
    return DraftRead(
        id=draft.id,
        contact_id=draft.contact_id,
        purpose=draft.purpose,
        platform=platform,
        variant_no=draft.variant_no,
        tone=draft.tone,
        subject=draft.subject,
        text=draft.text,
        status=draft.status.value,
        char_count=len(draft.text),
        char_limit=PLATFORM_CHAR_LIMITS.get(platform, 0),
        created_at=draft.created_at,
    )


def _contact_to_read(contact: Contact) -> ContactRead:
    return ContactRead(
        id=contact.id,
        name=contact.name,
        role=contact.role,
        company=contact.company,
        notes=contact.notes,
        created_at=contact.created_at,
        drafts=[_draft_to_read(d) for d in contact.drafts],
    )


# --------------------------------------------------------------------------- #
# Contact CRUD
# --------------------------------------------------------------------------- #


@router.post("/contacts", response_model=ContactRead, summary="Add a contact")
def create_contact(payload: ContactCreate, session: Session = Depends(get_session)) -> ContactRead:
    contact = Contact(**payload.model_dump())
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return _contact_to_read(contact)


@router.get("/contacts", response_model=list[ContactSummary], summary="List contacts")
def list_contacts(session: Session = Depends(get_session)) -> list[ContactSummary]:
    contacts = session.query(Contact).order_by(Contact.created_at.desc()).all()
    return [
        ContactSummary(
            id=c.id,
            name=c.name,
            role=c.role,
            company=c.company,
            created_at=c.created_at,
            draft_count=len(c.drafts),
        )
        for c in contacts
    ]


@router.get("/contacts/{contact_id}", response_model=ContactRead, summary="Open a contact")
def get_contact(contact_id: int, session: Session = Depends(get_session)) -> ContactRead:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No contact with id {contact_id}",
                "hint": "It may have been deleted.",
            },
        )
    return _contact_to_read(contact)


@router.patch("/contacts/{contact_id}", response_model=ContactRead, summary="Edit a contact")
def update_contact(
    contact_id: int, payload: ContactUpdate, session: Session = Depends(get_session)
) -> ContactRead:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No contact with id {contact_id}",
                "hint": "It may have been deleted.",
            },
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    session.commit()
    session.refresh(contact)
    return _contact_to_read(contact)


@router.delete(
    "/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a contact"
)
def delete_contact(contact_id: int, session: Session = Depends(get_session)) -> None:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No contact with id {contact_id}", "hint": "Nothing to delete."},
        )
    session.delete(contact)
    session.commit()


# --------------------------------------------------------------------------- #
# Draft generation + status
# --------------------------------------------------------------------------- #


def _default_target_role(session: Session, contact: Contact) -> str:
    """Best available target role: latest roadmap, else the contact's own role."""
    latest = session.query(RoadmapPlan).order_by(RoadmapPlan.updated_at.desc()).first()
    if latest is not None:
        return latest.target_role
    return contact.role or "a role in my field"


@router.post("/draft", summary="Generate outreach variants, streaming progress (SSE)")
async def draft_outreach(
    request: DraftRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Validate up front (hook required), then stream the three variants."""
    contact = session.get(Contact, request.contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No contact with id {request.contact_id}",
                "hint": "Add them first.",
            },
        )
    if not request.hook.strip():
        raise HTTPException(
            status_code=422,  # unprocessable content (starlette's named alias is deprecated)
            detail={
                "message": "A hook is required.",
                "hint": "Add one specific detail about this person (a project, a talk, "
                "a shared interest) so the message doesn't read like a template.",
            },
        )

    resume: ResumeVersion | None
    if request.resume_id is not None:
        resume = session.get(ResumeVersion, request.resume_id)
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": f"No resume with id {request.resume_id}",
                    "hint": "Save one first.",
                },
            )
    else:
        resume = session.query(ResumeVersion).order_by(ResumeVersion.id.desc()).first()

    target_role = (request.target_role or "").strip() or _default_target_role(session, contact)
    resume_id = resume.id if resume else None
    engine = session.get_bind()

    async def event_stream() -> AsyncIterator[str]:
        with Session(engine) as stream_session:
            contact_row = stream_session.get(Contact, request.contact_id)
            resume_row = (
                stream_session.get(ResumeVersion, resume_id) if resume_id is not None else None
            )
            try:
                task = asyncio.create_task(
                    outreach_service.create_outreach_drafts(
                        stream_session,
                        contact_row,
                        resume_row,
                        target_role,
                        purpose=request.purpose,
                        platform=request.platform,
                        hook=request.hook.strip(),
                    )
                )
                yield _sse("step", {"stage": "drafting", "detail": "Writing three variants…"})
                started = time.monotonic()
                while not task.done():
                    await asyncio.sleep(HEARTBEAT_SECONDS)
                    if task.done():
                        break
                    yield _sse("heartbeat", {"elapsed_s": int(time.monotonic() - started)})

                variants = await task

                drafts: list[OutreachDraft] = []
                for variant_no, variant in enumerate(variants, start=1):
                    row = OutreachDraft(
                        contact_id=contact_row.id,
                        purpose=request.purpose,
                        platform=OutreachPlatform(request.platform),
                        variant_no=variant_no,
                        tone=variant.tone,
                        subject=variant.subject,
                        text=variant.text,
                        status=OutreachStatus.DRAFT,
                    )
                    stream_session.add(row)
                    drafts.append(row)
                stream_session.commit()
                for row in drafts:
                    stream_session.refresh(row)

                yield _sse(
                    "done",
                    {
                        "contact_id": contact_row.id,
                        "target_role": target_role,
                        "drafts": [_draft_to_read(d).model_dump(mode="json") for d in drafts],
                    },
                )
            except OllamaError as exc:
                logger.warning("Outreach draft failed: %s", exc.message)
                yield _sse("error", {"message": exc.message, "hint": exc.hint})
            except Exception as exc:  # noqa: BLE001 - stream must not 500 mid-body
                logger.exception("Unexpected outreach failure")
                yield _sse(
                    "error",
                    {
                        "message": f"Outreach draft failed: {exc}",
                        "hint": "Check the backend logs and retry.",
                    },
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.patch("/drafts/{draft_id}", response_model=DraftRead, summary="Mark a draft sent/replied")
def update_draft_status(
    draft_id: int, update: DraftStatusUpdate, session: Session = Depends(get_session)
) -> DraftRead:
    draft = session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No draft with id {draft_id}", "hint": "Regenerate the drafts."},
        )
    draft.status = OutreachStatus(update.status)
    session.commit()
    session.refresh(draft)
    return _draft_to_read(draft)


@router.delete(
    "/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a draft"
)
def delete_draft(draft_id: int, session: Session = Depends(get_session)) -> None:
    draft = session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"No draft with id {draft_id}", "hint": "Nothing to delete."},
        )
    session.delete(draft)
    session.commit()
