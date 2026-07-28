"""Schemas for the networking / outreach drafter (Phase 3a, Prompt 3a.1).

`OutreachDraftResult` is handed to Ollama's `format` parameter, so its shape
matches prompts/outreach_draft_v1.txt: exactly three variants, each a tone plus
an optional subject (email only) and the message text.

Platform character limits are enforced in code after generation (the model is
asked to respect them but a 3B model does not reliably count characters), so the
limits live here as the single source of truth shared by the service and the API
read shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Purpose = Literal["cold", "referral", "thankyou", "followup"]
Platform = Literal["linkedin_note", "inmail", "email"]
Tone = Literal["concise-formal", "warm", "direct"]
Status = Literal["draft", "sent", "replied"]

# Hard limits enforced after generation. LinkedIn connection notes are capped at
# 300 by LinkedIn itself; the InMail/email caps keep drafts skimmable.
PLATFORM_CHAR_LIMITS: dict[str, int] = {
    "linkedin_note": 300,
    "inmail": 1000,
    "email": 1200,
}


# --------------------------------------------------------------------------- #
# LLM-constrained output  (prompts/outreach_draft_v1.txt)
# --------------------------------------------------------------------------- #


class OutreachVariant(BaseModel):
    tone: Tone
    subject: str | None = Field(
        default=None, description="Email subject line; null for other platforms"
    )
    text: str = Field(description="The message body, within the platform's character limit")


class OutreachDraftResult(BaseModel):
    """Ollama-constrained output: three variants per request.

    `min_length=3` becomes `minItems: 3` in the JSON schema handed to Ollama, so
    grammar-constrained decoding produces at least three variants — a plain
    prompt asking for three is not enough for a 3B model (a real run returned
    one). The service trims any extras back to three.
    """

    variants: list[OutreachVariant] = Field(default_factory=list, min_length=3)


# --------------------------------------------------------------------------- #
# Contacts (all fields typed by hand — no scraping, SOW 4.2)
# --------------------------------------------------------------------------- #


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class DraftRead(BaseModel):
    id: int
    contact_id: int
    purpose: str
    platform: str
    variant_no: int
    tone: str | None
    subject: str | None
    text: str
    status: str
    char_count: int
    char_limit: int
    created_at: datetime


class ContactSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str | None
    company: str | None
    created_at: datetime
    draft_count: int = 0


class ContactRead(BaseModel):
    id: int
    name: str
    role: str | None
    company: str | None
    notes: str | None
    created_at: datetime
    drafts: list[DraftRead] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Draft generation request / status update
# --------------------------------------------------------------------------- #


class DraftRequest(BaseModel):
    contact_id: int
    purpose: Purpose
    platform: Platform
    # The one specific personal detail that stops the draft reading like a
    # template. Required — the router rejects empty/whitespace with a hint.
    hook: str
    # Optional grounding overrides; default to the latest resume and the most
    # recent roadmap's target role so outreach benefits from the other modules.
    resume_id: int | None = None
    target_role: str | None = None


class DraftStatusUpdate(BaseModel):
    status: Status
