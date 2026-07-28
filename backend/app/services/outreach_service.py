"""Outreach draft generation (Phase 3a, Prompt 3a.1).

One LLM call (temperature 0.7) produces three toned variants, grounded via RAG
in the sender's resume profile and target role. Because a 3B model does not
reliably count characters, the platform limits are enforced in code afterwards:
an over-long variant is regenerated once with a focused "make it shorter"
prompt, and if it is still over, truncated at a sentence boundary.

The app never sends anything — it returns text the user copies into LinkedIn or
Gmail themselves (SOW 4.2). Contacts are typed by hand; nothing is scraped.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import rag
from app.llm.client import OllamaClient
from app.llm.prompts import render_prompt
from app.models import Contact, ResumeVersion
from app.models.base import SourceType
from app.schemas.outreach import PLATFORM_CHAR_LIMITS, OutreachDraftResult, OutreachVariant

logger = logging.getLogger(__name__)

RETRIEVE_TOP_K = 6
SKIP_RETRIEVAL_CHARS = 3500


def _truncate_at_sentence(text: str, limit: int) -> str:
    """Cut `text` to `limit` chars, preferring a sentence boundary.

    Falls back to the last word boundary with an ellipsis, so a hard cut never
    lands mid-word. The result is always <= limit.
    """
    if len(text) <= limit:
        return text
    window = text[:limit]
    # Prefer the last sentence end that is not right at the start.
    best = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if best > limit // 2:
        return window[: best + 1].rstrip()
    for ending in (".", "!", "?"):
        idx = window.rfind(ending)
        if idx > limit // 2:
            return window[: idx + 1].rstrip()
    # No usable sentence end — cut at the last space and mark the elision.
    space = window.rfind(" ")
    body = window[:space] if space > 0 else window[: limit - 1]
    return body.rstrip() + "…"


async def _shorten(client: OllamaClient, text: str, limit: int, platform: str) -> str:
    """Ask the model to rewrite `text` under `limit` characters, once."""
    prompt = (
        f"Rewrite this {platform.replace('_', ' ')} message so it is UNDER {limit} "
        "characters while keeping the specific personal detail and the ask. "
        "Reply with ONLY the message text — no quotes, no preamble.\n\n"
        f"{text}"
    )
    result = await client.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.5,
        timeout=get_settings().STRUCTURE_TIMEOUT,
    )
    return (result or "").strip()


async def _enforce_limit(
    client: OllamaClient, variant: OutreachVariant, platform: str
) -> OutreachVariant:
    """Bring one variant within the platform limit: regenerate once, else truncate."""
    limit = PLATFORM_CHAR_LIMITS[platform]
    # Subject lines belong to email only.
    if platform != "email":
        variant.subject = None

    if len(variant.text) <= limit:
        return variant

    logger.info(
        "Variant over %s limit (%d > %d); regenerating once", platform, len(variant.text), limit
    )
    shortened = await _shorten(client, variant.text, limit, platform)
    if shortened and len(shortened) <= limit:
        variant.text = shortened
    else:
        # Truncate whichever attempt is usable (the shorter rewrite if we got one).
        source = shortened if shortened else variant.text
        variant.text = _truncate_at_sentence(source, limit)
    return variant


async def create_outreach_drafts(
    session: Session,
    contact: Contact,
    resume: ResumeVersion | None,
    target_role: str,
    *,
    purpose: str,
    platform: str,
    hook: str,
    client: OllamaClient | None = None,
) -> list[OutreachVariant]:
    """Generate three toned, length-compliant outreach variants for one contact."""
    settings = get_settings()
    client = client or OllamaClient()

    # -- Ground the sender profile in the resume ---------------------------- #
    resume_context = ""
    if resume is not None:
        if len(resume.raw_text) <= SKIP_RETRIEVAL_CHARS:
            resume_context = resume.raw_text
        else:
            hits = await rag.retrieve(
                session,
                f"{target_role} {purpose}",
                source_ids={SourceType.RESUME: resume.id},
                top_k=RETRIEVE_TOP_K,
                client=client,
            )
            resume_context = rag.build_context_block(hits) or resume.raw_text[:3000]

    contact_json = {
        "name": contact.name,
        "role": contact.role,
        "company": contact.company,
        "notes": contact.notes,
    }

    prompt = render_prompt(
        "outreach_draft",
        purpose=purpose,
        platform=platform.replace("_", " "),
        char_limit=PLATFORM_CHAR_LIMITS[platform],
        contact_json=str(contact_json),
        hook=hook,
        resume_chunks=resume_context or "(no resume on file)",
        target_role=target_role,
    )

    result: OutreachDraftResult = await client.chat(
        [{"role": "user", "content": prompt}],
        # Outreach benefits from warmth and variety; grounding comes from the
        # hook, the recipient, and the resume context, not a cold temperature.
        temperature=settings.TEMPERATURE_CREATIVE,
        json_schema=OutreachDraftResult,
        timeout=settings.STRUCTURE_TIMEOUT,
    )

    # The schema forces at least three; keep exactly three, trimming any extras.
    variants = [await _enforce_limit(client, v, platform) for v in result.variants[:3]]
    logger.info(
        "Drafted %d outreach variants for contact=%d (%s/%s)",
        len(variants),
        contact.id,
        purpose,
        platform,
    )
    return variants
