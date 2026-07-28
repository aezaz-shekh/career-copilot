"""Deterministic ATS-readability checklist (Phase 1, Prompt 1.3, stage 4).

An Applicant Tracking System parses a resume mechanically: it looks for standard
headings, readable contact details, dates it can parse, and a sane length. Those
are structural facts about the document, so they are checked in code, not by the
model. Three reasons this is the right call:

  * Consistency — SOW Section 7 requires repeatable output; a rule returns the
    same verdict every time, an LLM does not.
  * Speed — every LLM call is ~100 s on this CPU-only machine. This check is
    instant, so it does not add a fourth slow stage to the review.
  * Reliability — "does the resume contain an email address" is exactly the kind
    of yes/no a regex answers perfectly and a 3B model sometimes fluffs.

The checks read the parsed sections where possible and fall back to the raw text,
so a resume saved without structuring still gets a verdict.
"""

from __future__ import annotations

import re

from app.schemas.resume import ParsedResume
from app.schemas.review import AtsCheck, AtsChecklist

# One line of a resume that looks like a date range: "May 2025", "2023 - 2026",
# "Jan 2024 – Present". Enough to confirm dates are machine-readable.
_DATE = re.compile(
    r"(19|20)\d{2}|"  # a bare year
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}|"
    r"present|current",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# A candidate phone-like run of digits/separators.
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def _looks_like_phone(text: str) -> bool:
    """True if the text holds a phone-shaped number.

    Requires at least 10 digits in the run, so a date range like "2023 - 2026"
    (8 digits) is not mistaken for a phone number.
    """
    for candidate in _PHONE_CANDIDATE.findall(text):
        if sum(char.isdigit() for char in candidate) >= 10:
            return True
    return False


# Headings an ATS recognises. We look for these as whole words in the raw text.
_STANDARD_HEADINGS = [
    "experience",
    "education",
    "skills",
    "projects",
    "summary",
    "objective",
    "certification",
]

MIN_WORDS = 150  # below this a resume is too thin to parse meaningfully
MAX_WORDS = 1200  # above ~2 pages ATS relevance and recruiter attention drop


def _check_contact(parsed: ParsedResume | None, raw_text: str) -> AtsCheck:
    email = None
    if parsed and parsed.contact.email:
        email = parsed.contact.email
    else:
        match = _EMAIL.search(raw_text)
        email = match.group(0) if match else None

    has_phone = bool(parsed and parsed.contact.phone) or _looks_like_phone(raw_text)

    if email and has_phone:
        return AtsCheck(
            name="Contact information", passed=True, detail="Email and phone both found."
        )
    if email or has_phone:
        found = "email" if email else "phone"
        return AtsCheck(
            name="Contact information",
            passed=True,
            detail=f"Found {found}. Add the other so recruiters can reach you either way.",
        )
    return AtsCheck(
        name="Contact information",
        passed=False,
        detail="No email or phone detected. Add both near the top of the resume.",
    )


def _check_headings(raw_text: str) -> AtsCheck:
    lowered = raw_text.lower()
    found = [h for h in _STANDARD_HEADINGS if re.search(rf"\b{h}", lowered)]
    # Experience/skills/education are the ones an ATS most relies on.
    core_present = {"experience", "skills", "education"}.intersection(found)

    if len(core_present) >= 2:
        return AtsCheck(
            name="Standard section headings",
            passed=True,
            detail=f"Recognised headings: {', '.join(sorted(found))}.",
        )
    return AtsCheck(
        name="Standard section headings",
        passed=False,
        detail=(
            "Few standard headings found. Use clear headings like EXPERIENCE, "
            "EDUCATION and SKILLS so an ATS can segment the resume."
        ),
    )


def _check_dates(parsed: ParsedResume | None, raw_text: str) -> AtsCheck:
    if parsed and (parsed.experience or parsed.education):
        dated = sum(1 for item in parsed.experience if item.start_date or item.end_date) + sum(
            1 for item in parsed.education if item.start_date or item.end_date
        )
        total = len(parsed.experience) + len(parsed.education)
        if total and dated >= max(1, total // 2):
            return AtsCheck(
                name="Parseable dates",
                passed=True,
                detail=f"{dated} of {total} entries have readable dates.",
            )

    matches = len(_DATE.findall(raw_text))
    if matches >= 2:
        return AtsCheck(
            name="Parseable dates",
            passed=True,
            detail=f"Found {matches} date-like values in a standard format.",
        )
    return AtsCheck(
        name="Parseable dates",
        passed=False,
        detail="Few readable dates found. Use a format like 'May 2025 - Present'.",
    )


def _check_length(raw_text: str) -> AtsCheck:
    words = len(raw_text.split())
    if words < MIN_WORDS:
        return AtsCheck(
            name="Length",
            passed=False,
            detail=f"Only {words} words. A resume this short usually lacks the detail "
            "recruiters expect.",
        )
    if words > MAX_WORDS:
        return AtsCheck(
            name="Length",
            passed=False,
            detail=f"{words} words is long (over ~2 pages). Tighten to the most relevant content.",
        )
    return AtsCheck(
        name="Length",
        passed=True,
        detail=f"{words} words — a sensible one-to-two page length.",
    )


def _check_structure_dependence(parsed: ParsedResume | None, raw_text: str) -> AtsCheck:
    """A proxy for 'does not depend on tables/images to be read'.

    We cannot see the original layout here, but if we recovered clean text with
    real sentences, the content did not hide inside an image. Very low word
    counts relative to the file are the tell of an image-only resume, which the
    upload step already warns about; here we confirm text is present and prose-like.
    """
    words = raw_text.split()
    if len(words) < MIN_WORDS:
        return AtsCheck(
            name="Text is machine-readable (not image/table dependent)",
            passed=False,
            detail="Very little extractable text — the resume may rely on images "
            "or complex tables.",
        )
    # If structuring recovered bullets, the content is plainly text, not an image.
    recovered = bool(parsed and (parsed.experience or parsed.projects))
    detail = (
        "Text extracted cleanly and structured into sections."
        if recovered
        else "Text extracted cleanly. Avoid multi-column tables and text inside images."
    )
    return AtsCheck(
        name="Text is machine-readable (not image/table dependent)",
        passed=True,
        detail=detail,
    )


def run_ats_checks(raw_text: str, parsed: ParsedResume | None = None) -> AtsChecklist:
    """Run every ATS check and return the checklist with a pass tally."""
    checks = [
        _check_contact(parsed, raw_text),
        _check_headings(raw_text),
        _check_dates(parsed, raw_text),
        _check_structure_dependence(parsed, raw_text),
        _check_length(raw_text),
    ]
    passed = sum(1 for check in checks if check.passed)
    return AtsChecklist(checks=checks, passed_count=passed, total=len(checks))
