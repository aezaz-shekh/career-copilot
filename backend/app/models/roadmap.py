"""Career roadmap models (SOW Section 6.3).

The SOW names two entities here, RoadmapPlan *and* RoadmapItem, while the
prompt playbook lists only RoadmapPlan with a `plan_json` blob. Both are kept:

- `plan_json` preserves the model's original generated plan verbatim, which the
  evaluation harness needs to compare prompt revisions.
- `RoadmapItem` rows are the user-editable copy. SOW objective O4 requires the
  roadmap to be "persisted and editable over time", and ticking off one action
  is a row update rather than a read-modify-write of a whole JSON document.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, RoadmapHorizon, enum_column, utcnow


class RoadmapPlan(Base):
    """A skill-gap analysis and phased learning plan for one target role."""

    __tablename__ = "roadmap_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_role: Mapped[str] = mapped_column(String(200), nullable=False)
    current_profile: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The model's original output, kept unedited as an evaluation baseline.
    plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    items: Mapped[list[RoadmapItem]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="RoadmapItem.position",
    )

    def __repr__(self) -> str:
        return f"<RoadmapPlan id={self.id} target_role={self.target_role!r}>"


class RoadmapItem(Base):
    """One concrete action within a roadmap phase."""

    __tablename__ = "roadmap_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("roadmap_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    horizon: Mapped[RoadmapHorizon] = mapped_column(enum_column(RoadmapHorizon), nullable=False)
    skill: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    plan: Mapped[RoadmapPlan] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<RoadmapItem id={self.id} horizon={self.horizon.value} skill={self.skill!r}>"
