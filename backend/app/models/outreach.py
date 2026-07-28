"""Networking contact and outreach draft models (SOW Section 6.3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OutreachPlatform, OutreachStatus, enum_column, utcnow


class Contact(Base):
    """A person the user wants to reach out to.

    Every field is typed in by hand. Nothing here is ever scraped from LinkedIn
    or any job board — SOW Section 4.2 rules that out on Terms-of-Service grounds.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # The "hook": a specific detail about this person. SOW Section 11 makes at
    # least one specific detail mandatory before generation, because without it
    # a 3B model produces drafts that read like a template.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    drafts: Mapped[list[OutreachDraft]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
        order_by="OutreachDraft.variant_no",
    )

    def __repr__(self) -> str:
        return f"<Contact id={self.id} name={self.name!r}>"


class OutreachDraft(Base):
    """One generated message variant for one contact.

    The app never sends these. The user copies the final text into LinkedIn or
    Gmail themselves (SOW Section 4.2), and `status` tracks what happened next.
    """

    __tablename__ = "outreach_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    platform: Mapped[OutreachPlatform] = mapped_column(
        enum_column(OutreachPlatform), nullable=False
    )

    # 2-3 variants are generated per request so the user edits rather than
    # copies verbatim (SOW Section 11, generic-draft risk).
    variant_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Each variant carries a distinct tone (concise-formal / warm / direct) and,
    # for email only, a subject line. Added in Phase 3a — see db.ensure_columns.
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[OutreachStatus] = mapped_column(
        enum_column(OutreachStatus), default=OutreachStatus.DRAFT, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    contact: Mapped[Contact] = relationship(back_populates="drafts")

    def __repr__(self) -> str:
        return f"<OutreachDraft id={self.id} platform={self.platform.value} v{self.variant_no}>"
