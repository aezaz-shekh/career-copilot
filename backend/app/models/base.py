"""Declarative base, shared enums, and timestamp helpers for the ORM layer.

All persistence goes through SQLAlchemy, which parameterises every statement —
that is how SOW Section 7 ("parameterized SQL throughout") is satisfied by
construction rather than by review.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit constraint names. SQLite cannot ALTER a constraint, so predictable
# names are what make a future migration (or a manual fix) tractable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    """Timezone-aware current time, used as the default for every timestamp."""
    return datetime.now(UTC)


def enum_column(enum_class: type[enum.Enum]) -> SAEnum:
    """Build the column type used for every enum in this schema.

    Three settings, each deliberate:

    - `native_enum=False` — SQLite has no ENUM type, so this becomes VARCHAR
      plus a CHECK constraint. Invalid values are rejected by the database
      itself, not merely by application code.
    - `values_callable` — SQLAlchemy otherwise persists the member *name*
      (`"TEXT"`), whereas the specification calls for the member *value*
      (`"text"`). Without this the stored data would not match the SOW, and
      anyone opening the .db file would see shouty uppercase strings.
    - `validate_strings=True` — rejects an unknown raw string on the way in
      rather than at read time.
    """
    return SAEnum(
        enum_class,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class SourceType(enum.StrEnum):
    """What a text chunk was extracted from."""

    RESUME = "resume"
    JD = "jd"


class InterviewMode(enum.StrEnum):
    """How an interview turn was delivered.

    Stored per turn as well as per session, because SOW Section 12 requires
    proving that the same answer scores within +/-1 point via voice vs. text —
    which is only measurable if the delivery mode is recorded on the turn.
    """

    TEXT = "text"
    VOICE = "voice"


class RoadmapHorizon(enum.StrEnum):
    """Phases of the learning roadmap (SOW Section 4.1, module 4)."""

    NOW = "now"
    THREE_MONTH = "3_month"
    TWELVE_MONTH = "12_month"


class OutreachPlatform(enum.StrEnum):
    """Target platform for an outreach draft.

    LINKEDIN_NOTE carries a hard 300-character limit (SOW Section 4.2, O5),
    which is why the platform is a constrained value and not free text.
    """

    LINKEDIN_NOTE = "linkedin_note"
    INMAIL = "inmail"
    EMAIL = "email"


class OutreachStatus(enum.StrEnum):
    """Where a draft has got to."""

    DRAFT = "draft"
    SENT = "sent"
    REPLIED = "replied"
