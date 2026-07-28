"""Dual-parser text extraction for resumes (SOW Section 5 and Section 11).

PyMuPDF is fast and handles most PDFs. pdfplumber is slower but lays out
table-based and multi-column resumes better. Neither wins every time, so the
strategy is: run PyMuPDF, judge the result, and fall back to pdfplumber only
when the first result looks broken.

"Looks broken" is a heuristic, not a certainty, which is why a low quality score
never blocks the upload. It sets a warning, and the mandatory manual-edit step
in the UI lets the user fix whatever the parser got wrong. That combination is
the SOW Section 11 mitigation for PDF layout variance.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

# --- Heuristic thresholds -------------------------------------------------- #
# Tuned against real resumes: a one-page CV holds roughly 2,000-4,000 characters.
MIN_TOTAL_CHARS = 200  # below this, extraction essentially failed
MIN_CHARS_PER_PAGE = 100  # a scanned/image-only page yields almost nothing
MIN_ALPHA_RATIO = 0.55  # symbol soup means a broken font mapping
MAX_SINGLE_CHAR_WORD_RATIO = 0.35  # "H e l l o" spacing from bad CID tables
MAX_REPLACEMENT_CHARS = 20  # U+FFFD means undecodable glyphs

_WORD = re.compile(r"\S+")


class ResumeParseError(Exception):
    """The file could not be read at all, with an actionable reason."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass
class TextQuality:
    """Verdict on one extraction attempt."""

    is_usable: bool
    character_count: int
    page_count: int
    alpha_ratio: float
    single_char_word_ratio: float
    warnings: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Rough 0-1 confidence, used only to pick between two attempts."""
        if self.character_count == 0:
            return 0.0
        return round(
            min(1.0, self.character_count / max(1, self.page_count) / 2000)
            * self.alpha_ratio
            * (1.0 - self.single_char_word_ratio),
            4,
        )


@dataclass
class ExtractionResult:
    """Final extraction outcome handed back to the router."""

    text: str
    parser_used: str
    fallback_used: bool
    quality: TextQuality


def assess_text_quality(text: str, page_count: int) -> TextQuality:
    """Judge whether extracted text is usable, and say why if not.

    Four independent failure modes are checked, because they need different
    advice: an empty result means a scanned PDF, while symbol soup means a
    broken embedded font.
    """
    stripped = text.strip()
    total = len(stripped)
    warnings: list[str] = []

    words = _WORD.findall(stripped)
    single_char_words = sum(1 for word in words if len(word) == 1)
    single_char_ratio = single_char_words / len(words) if words else 0.0

    alpha = sum(1 for char in stripped if char.isalpha() or char.isspace())
    alpha_ratio = alpha / total if total else 0.0

    replacements = stripped.count("�")

    if total < MIN_TOTAL_CHARS:
        warnings.append(
            "Almost no text could be read. This is usually a scanned or "
            "image-only PDF, which has no text layer to extract."
        )
    elif page_count and total / page_count < MIN_CHARS_PER_PAGE:
        warnings.append(
            f"Only {total // max(1, page_count)} characters per page were found, "
            "which suggests parts of the document are images."
        )

    if alpha_ratio < MIN_ALPHA_RATIO and total >= MIN_TOTAL_CHARS:
        warnings.append(
            "The text is mostly symbols rather than letters, which usually means "
            "the PDF uses an embedded font that cannot be mapped back to characters."
        )

    if single_char_ratio > MAX_SINGLE_CHAR_WORD_RATIO and len(words) > 20:
        warnings.append(
            "Words appear to be split into single characters. The spacing "
            "information in this PDF is unreliable."
        )

    if replacements > MAX_REPLACEMENT_CHARS:
        warnings.append(
            f"{replacements} characters could not be decoded and appear as placeholders."
        )

    return TextQuality(
        is_usable=not warnings,
        character_count=total,
        page_count=page_count,
        alpha_ratio=round(alpha_ratio, 4),
        single_char_word_ratio=round(single_char_ratio, 4),
        warnings=warnings,
    )


def extract_with_pymupdf(data: bytes) -> tuple[str, int]:
    """Primary extractor: fast, good on ordinary single-column resumes."""
    with fitz.open(stream=data, filetype="pdf") as document:
        if document.is_encrypted and not document.authenticate(""):
            raise ResumeParseError(
                "The PDF is password protected",
                hint="Remove the password, or copy the text and paste it in manually.",
            )
        pages = [page.get_text("text") for page in document]
        return "\n".join(pages), document.page_count


def extract_with_pdfplumber(data: bytes) -> tuple[str, int]:
    """Fallback extractor: slower, better on multi-column and table layouts."""
    with pdfplumber.open(io.BytesIO(data)) as document:
        pages = [page.extract_text() or "" for page in document.pages]
        return "\n".join(pages), len(document.pages)


def extract_text_from_pdf(data: bytes) -> ExtractionResult:
    """Extract PDF text, falling back to the second parser when needed.

    If both parsers produce questionable text, the better of the two is returned
    with its warnings attached rather than an error — the user can still fix it
    by hand, and refusing the file outright would help nobody.
    """
    try:
        primary_text, pages = extract_with_pymupdf(data)
    except ResumeParseError:
        raise
    except Exception as exc:
        logger.warning("PyMuPDF failed outright, trying pdfplumber: %s", exc)
        primary_text, pages = "", 0

    primary_quality = assess_text_quality(primary_text, pages)

    if primary_quality.is_usable:
        return ExtractionResult(
            text=primary_text,
            parser_used="pymupdf",
            fallback_used=False,
            quality=primary_quality,
        )

    logger.info(
        "PyMuPDF output looked broken (score=%.3f); falling back to pdfplumber",
        primary_quality.score,
    )

    try:
        fallback_text, fallback_pages = extract_with_pdfplumber(data)
    except Exception as exc:
        logger.warning("pdfplumber also failed: %s", exc)
        if not primary_text.strip():
            raise ResumeParseError(
                "No readable text could be extracted from this PDF",
                hint=(
                    "This is usually a scanned document. Open the PDF, select the "
                    "text and paste it into the box below instead."
                ),
            ) from exc
        return ExtractionResult(
            text=primary_text,
            parser_used="pymupdf",
            fallback_used=True,
            quality=primary_quality,
        )

    fallback_quality = assess_text_quality(fallback_text, fallback_pages or pages)

    # Keep whichever attempt scored higher — the fallback is not automatically better.
    if fallback_quality.score >= primary_quality.score:
        if not fallback_text.strip():
            raise ResumeParseError(
                "No readable text could be extracted from this PDF",
                hint=(
                    "This is usually a scanned document. Open the PDF, select the "
                    "text and paste it into the box below instead."
                ),
            )
        return ExtractionResult(
            text=fallback_text,
            parser_used="pdfplumber",
            fallback_used=True,
            quality=fallback_quality,
        )

    return ExtractionResult(
        text=primary_text,
        parser_used="pymupdf",
        fallback_used=True,
        quality=primary_quality,
    )


def extract_text_from_txt(data: bytes) -> ExtractionResult:
    """Decode a plain-text upload, tolerating non-UTF-8 encodings."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Windows exports are often cp1252; replace anything still undecodable
        # so the user sees the text and can fix it, rather than getting an error.
        text = data.decode("cp1252", errors="replace")
        logger.info("Text file was not UTF-8; decoded as cp1252")

    quality = assess_text_quality(text, page_count=1)
    return ExtractionResult(
        text=text, parser_used="plaintext", fallback_used=False, quality=quality
    )


def extract_text(data: bytes, filename: str) -> ExtractionResult:
    """Dispatch on file extension and extract text."""
    if not data:
        raise ResumeParseError(
            "The uploaded file is empty", hint="Choose a file that contains your resume."
        )

    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if suffix == "pdf":
        return extract_text_from_pdf(data)
    if suffix in {"txt", "text", "md"}:
        return extract_text_from_txt(data)

    raise ResumeParseError(
        f"Unsupported file type: .{suffix or 'unknown'}",
        hint="Upload a PDF or a .txt file, or paste your resume text directly.",
    )
