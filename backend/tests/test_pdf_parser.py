"""Tests for dual-parser text extraction and the fallback heuristic.

The two required by the phase brief are `test_fallback_triggers_when_primary_output_is_broken`
and (in test_resume_ingestion.py) the schema-validation test. The rest pin the
heuristic thresholds, which are the part most likely to drift.
"""

from __future__ import annotations

import fitz
import pytest

from app.services import pdf_parser
from app.services.pdf_parser import (
    ResumeParseError,
    assess_text_quality,
    extract_text,
    extract_text_from_pdf,
)

GOOD_RESUME_TEXT = (
    "AARAV SHARMA\n"
    "Ahmedabad, Gujarat | aarav@example.com | +91 98XXXXXX21\n\n"
    "EDUCATION\n"
    "Bachelor of Computer Applications, Gujarat University, 2023 - 2026, CGPA 8.4\n\n"
    "TECHNICAL SKILLS\n"
    "Languages: Python, JavaScript, SQL. Web: React, Flask, REST APIs.\n\n"
    "PROJECTS\n"
    "Library Management System: built a Flask application tracking 4000 titles "
    "with a normalised MySQL schema of seven tables and sub-five-second search.\n\n"
    "EXPERIENCE\n"
    "Web Development Intern, Nexus Softwares, May 2025 to July 2025. Fixed more "
    "than twenty front-end defects in a React dashboard and wrote SQL for the "
    "monthly reporting module used by the operations team.\n"
)


def make_pdf(text: str) -> bytes:
    """Build a real single-page PDF containing `text`."""
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 560, 780), text, fontsize=10)
    data = document.tobytes()
    document.close()
    return data


# --------------------------------------------------------------------------- #
# Quality heuristic
# --------------------------------------------------------------------------- #


def test_clean_text_is_judged_usable() -> None:
    quality = assess_text_quality(GOOD_RESUME_TEXT, page_count=1)

    assert quality.is_usable
    assert quality.warnings == []
    assert quality.character_count > 200


def test_empty_extraction_is_flagged_as_scanned_pdf() -> None:
    quality = assess_text_quality("   \n  ", page_count=2)

    assert not quality.is_usable
    assert any("scanned" in warning for warning in quality.warnings)


def test_symbol_soup_is_flagged() -> None:
    """A broken embedded font maps glyphs to punctuation rather than letters."""
    quality = assess_text_quality("#$%&*()!@" * 60, page_count=1)

    assert not quality.is_usable
    assert any("symbols" in warning for warning in quality.warnings)


def test_character_spaced_text_is_flagged() -> None:
    """Bad CID tables produce 'A A R A V   S H A R M A'."""
    text = " ".join("thisistheresumetextspacedoutbadly" * 8)
    quality = assess_text_quality(text, page_count=1)

    assert not quality.is_usable
    assert any("single characters" in warning for warning in quality.warnings)


def test_undecodable_characters_are_flagged() -> None:
    quality = assess_text_quality(GOOD_RESUME_TEXT + "�" * 25, page_count=1)

    assert any("could not be decoded" in warning for warning in quality.warnings)


# --------------------------------------------------------------------------- #
# Fallback orchestration  (required test #1)
# --------------------------------------------------------------------------- #


def test_fallback_triggers_when_primary_output_is_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    """PyMuPDF returns garbage, so pdfplumber runs and its result is used."""
    calls: list[str] = []

    def broken_pymupdf(data: bytes) -> tuple[str, int]:
        calls.append("pymupdf")
        return "#$%&*()!@" * 60, 1

    def working_pdfplumber(data: bytes) -> tuple[str, int]:
        calls.append("pdfplumber")
        return GOOD_RESUME_TEXT, 1

    monkeypatch.setattr(pdf_parser, "extract_with_pymupdf", broken_pymupdf)
    monkeypatch.setattr(pdf_parser, "extract_with_pdfplumber", working_pdfplumber)

    result = extract_text_from_pdf(b"%PDF-fake")

    assert calls == ["pymupdf", "pdfplumber"]
    assert result.parser_used == "pdfplumber"
    assert result.fallback_used is True
    assert result.quality.is_usable
    assert "AARAV SHARMA" in result.text


def test_fallback_does_not_trigger_when_primary_output_is_good(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The slow parser must not run when the fast one already succeeded."""
    calls: list[str] = []

    monkeypatch.setattr(
        pdf_parser,
        "extract_with_pymupdf",
        lambda data: (calls.append("pymupdf"), (GOOD_RESUME_TEXT, 1))[1],
    )
    monkeypatch.setattr(
        pdf_parser,
        "extract_with_pdfplumber",
        lambda data: (calls.append("pdfplumber"), (GOOD_RESUME_TEXT, 1))[1],
    )

    result = extract_text_from_pdf(b"%PDF-fake")

    assert calls == ["pymupdf"]
    assert result.parser_used == "pymupdf"
    assert result.fallback_used is False


def test_better_of_two_bad_results_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback is not automatically better — the higher score wins.

    Primary: 240 usable characters spread over 3 pages, so it trips the
    chars-per-page warning and triggers a fallback. Fallback: almost nothing.
    The primary text is the more useful of the two, so it must be what is kept.
    """
    monkeypatch.setattr(
        pdf_parser, "extract_with_pymupdf", lambda data: ("Partial resume text " * 12, 3)
    )
    monkeypatch.setattr(pdf_parser, "extract_with_pdfplumber", lambda data: ("x", 3))

    result = extract_text_from_pdf(b"%PDF-fake")

    assert result.parser_used == "pymupdf"
    assert result.fallback_used is True  # a fallback was attempted, then rejected
    assert "Partial resume text" in result.text


def test_both_parsers_empty_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_parser, "extract_with_pymupdf", lambda data: ("", 3))
    monkeypatch.setattr(pdf_parser, "extract_with_pdfplumber", lambda data: ("", 3))

    with pytest.raises(ResumeParseError) as exc_info:
        extract_text_from_pdf(b"%PDF-fake")

    assert "paste" in exc_info.value.hint.lower()


# --------------------------------------------------------------------------- #
# Real files
# --------------------------------------------------------------------------- #


def test_real_pdf_round_trip() -> None:
    """A genuine PDF built here, extracted by the real PyMuPDF path."""
    result = extract_text(make_pdf(GOOD_RESUME_TEXT), "resume.pdf")

    assert result.parser_used == "pymupdf"
    assert result.fallback_used is False
    assert "AARAV SHARMA" in result.text
    assert "Library Management System" in result.text
    assert result.quality.is_usable


def test_plain_text_upload() -> None:
    result = extract_text(GOOD_RESUME_TEXT.encode("utf-8"), "resume.txt")

    assert result.parser_used == "plaintext"
    assert "AARAV SHARMA" in result.text


def test_non_utf8_text_is_decoded_not_rejected() -> None:
    """Windows exports are often cp1252; a smart quote must not break upload."""
    result = extract_text("Résumé — Aarav's CV. ".encode("cp1252") * 20, "resume.txt")

    assert "Aarav" in result.text


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ResumeParseError, match="empty"):
        extract_text(b"", "resume.pdf")


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(ResumeParseError) as exc_info:
        extract_text(b"PK\x03\x04somedocx", "resume.docx")

    assert "PDF" in exc_info.value.hint


def test_corrupt_pdf_falls_through_to_an_actionable_error() -> None:
    """A file claiming to be a PDF but isn't must not surface a raw traceback."""
    with pytest.raises(ResumeParseError):
        extract_text(b"this is definitely not a pdf", "resume.pdf")
