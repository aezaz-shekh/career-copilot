"""Resume structuring: raw text in, validated sections out."""

from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.llm.client import OllamaClient
from app.llm.prompts import render_prompt
from app.schemas.resume import ParsedResume

logger = logging.getLogger(__name__)

PROMPT_NAME = "resume_parser"

# Pinned deliberately rather than floating to the newest file.
#
# v2 was written to fix v1 missing the EXPERIENCE section. It did fix that, and
# it fixed contact.name, but it regressed three other fields: projects dropped
# from 3 to 0, certifications from 1 to 0, and contact.email picked up the phone
# number. Measured on the same resume: v1 scored 5/7 fields correct, v2 scored
# 3/7, and v2 was 30% slower. The comparison table is in prompts/README.md.
#
# Raise this only when a measurement says the newer version is actually better.
PROMPT_VERSION = 1


async def structure_resume(
    raw_text: str, client: OllamaClient | None = None
) -> tuple[ParsedResume, int]:
    """Break raw resume text into sections using the local model.

    Runs at TEMPERATURE_SCORING (0.2) rather than the creative temperature: this
    is an extraction task, and sampling variety here means invented content.

    Returns:
        The validated sections, and how many milliseconds generation took.
    """
    settings = get_settings()
    client = client or OllamaClient()

    prompt = render_prompt(PROMPT_NAME, version=PROMPT_VERSION, resume_text=raw_text)

    started = time.perf_counter()
    parsed = await client.chat(
        [{"role": "user", "content": prompt}],
        temperature=settings.TEMPERATURE_SCORING,
        json_schema=ParsedResume,
        timeout=settings.STRUCTURE_TIMEOUT,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "Structured resume in %d ms: %d experience, %d education, %d skills, %d projects",
        elapsed_ms,
        len(parsed.experience),
        len(parsed.education),
        len(parsed.skills),
        len(parsed.projects),
    )
    return parsed, elapsed_ms
