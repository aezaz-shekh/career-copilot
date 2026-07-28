"""Tests for the deterministic ATS checklist."""

from __future__ import annotations

from app.schemas.resume import ContactInfo, EducationItem, ExperienceItem, ParsedResume
from app.services.ats import run_ats_checks

GOOD_RESUME = (
    "AARAV SHARMA\n"
    "aarav.sharma@example.com | +91 9812345621\n\n"
    "EDUCATION\n"
    "Bachelor of Computer Applications, Gujarat University, 2023 - 2026\n\n"
    "EXPERIENCE\n"
    "Web Development Intern, Nexus Softwares, May 2025 - July 2025. "
    "Fixed twenty front-end defects in a React dashboard and wrote SQL for "
    "the monthly reporting module used by the operations team every week.\n\n"
    "SKILLS\n"
    "Python, JavaScript, SQL, React, Flask, Git. "
) * 3


def check(checklist, name):
    return next(c for c in checklist.checks if c.name.startswith(name))


def test_clean_resume_passes_every_check() -> None:
    result = run_ats_checks(GOOD_RESUME)

    assert result.total == 5
    assert result.passed_count == 5
    assert all(c.passed for c in result.checks)


def test_missing_contact_fails_that_check_only() -> None:
    text = GOOD_RESUME.replace("aarav.sharma@example.com | +91 9812345621", "")

    result = run_ats_checks(text)

    assert check(result, "Contact").passed is False
    assert result.passed_count < result.total


def test_no_headings_fails_headings_check() -> None:
    text = (
        "Aarav Sharma. aarav@example.com. +91 9812345621. "
        "I did some work in 2025 and studied things. " * 20
    )

    result = run_ats_checks(text)

    assert check(result, "Standard section").passed is False


def test_too_short_fails_length() -> None:
    result = run_ats_checks("Aarav Sharma aarav@example.com +91 9812345621 Python 2025")

    length = check(result, "Length")
    assert length.passed is False
    assert "short" in length.detail.lower()


def test_too_long_fails_length() -> None:
    result = run_ats_checks("word " * 1400 + " aarav@example.com +91 9812345621 EXPERIENCE 2025")

    assert check(result, "Length").passed is False


def test_missing_dates_fails_dates_check() -> None:
    text = (
        "AARAV SHARMA aarav@example.com +91 9812345621 "
        "EXPERIENCE Worked as an intern doing React and SQL. "
        "EDUCATION Studied computer applications. SKILLS Python React. " * 6
    )

    result = run_ats_checks(text)

    assert check(result, "Parseable dates").passed is False


def test_parsed_sections_improve_the_verdict() -> None:
    """Structured data lets the check confirm dates and structure directly."""
    parsed = ParsedResume(
        contact=ContactInfo(name="Aarav", email="a@example.com", phone="+91 9812345621"),
        experience=[
            ExperienceItem(
                role="Intern",
                company="Nexus",
                start_date="May 2025",
                end_date="Jul 2025",
                bullets=["Built a React dashboard"],
            )
        ],
        education=[
            EducationItem(degree="BCA", institution="GU", start_date="2023", end_date="2026")
        ],
        skills=["Python", "SQL"],
    )

    result = run_ats_checks(GOOD_RESUME, parsed)

    assert check(result, "Parseable dates").passed is True
    assert check(result, "Text is machine-readable").passed is True
