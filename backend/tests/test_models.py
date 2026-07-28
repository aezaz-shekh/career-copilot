"""Schema tests: relationships, cascades, enum constraints, and vector search.

Each test gets its own SQLite file in a temp directory, so nothing here touches
the real database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import VEC_TABLE, create_db_engine, init_db, vec_version
from app.models import (
    Contact,
    EmbeddingChunk,
    InterviewMode,
    InterviewSession,
    InterviewTurn,
    JobDescription,
    OutreachDraft,
    OutreachPlatform,
    OutreachStatus,
    ResumeVersion,
    RoadmapHorizon,
    RoadmapItem,
    RoadmapPlan,
    SourceType,
)
from app.services import vector_store


@pytest.fixture
def session(tmp_path) -> Session:
    """A session against a throwaway database with the full schema created."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_vector(fill: float = 0.1) -> list[float]:
    return [fill] * get_settings().EMBED_DIM


# --------------------------------------------------------------------------- #
# Schema creation
# --------------------------------------------------------------------------- #


def test_init_db_creates_every_table(session: Session) -> None:
    rows = session.execute(
        text("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
    ).all()
    names = {row[0] for row in rows}

    for expected in (
        "resume_versions",
        "job_descriptions",
        "interview_sessions",
        "interview_turns",
        "roadmap_plans",
        "roadmap_items",
        "contacts",
        "outreach_drafts",
        "embedding_chunks",
        VEC_TABLE,
    ):
        assert expected in names, f"missing table: {expected}"


def test_init_db_is_idempotent(tmp_path) -> None:
    """Startup calls this every time; a second call must not fail or wipe data."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as session:
        session.add(ResumeVersion(title="Keep me", raw_text="text"))
        session.commit()

    init_db(engine)

    with Session(engine) as session:
        assert session.query(ResumeVersion).count() == 1
    engine.dispose()


def test_sqlite_vec_extension_is_loaded(session: Session) -> None:
    assert vec_version(session.get_bind()).startswith("v")


def test_foreign_keys_are_enforced(session: Session) -> None:
    """SQLite disables FK enforcement by default; app/db.py turns it back on."""
    session.add(InterviewTurn(session_id=9999, question="orphan"))
    with pytest.raises(IntegrityError):
        session.commit()


# --------------------------------------------------------------------------- #
# Entities and relationships
# --------------------------------------------------------------------------- #


def test_resume_and_jd_round_trip(session: Session) -> None:
    resume = ResumeVersion(
        title="v1", raw_text="Python developer", parsed_json={"skills": ["Python", "SQL"]}
    )
    jd = JobDescription(title="Junior Dev", company="TechNova", raw_text="We need Python")
    session.add_all([resume, jd])
    session.commit()

    stored = session.get(ResumeVersion, resume.id)
    assert stored.parsed_json == {"skills": ["Python", "SQL"]}
    assert stored.created_at is not None
    assert session.get(JobDescription, jd.id).company == "TechNova"


def test_interview_turns_cascade_on_session_delete(session: Session) -> None:
    interview = InterviewSession(mode=InterviewMode.VOICE)
    interview.turns = [
        InterviewTurn(
            question="Tell me about yourself", answer="I am...", mode=InterviewMode.VOICE
        ),
        InterviewTurn(question="Describe a challenge", mode=InterviewMode.TEXT),
    ]
    session.add(interview)
    session.commit()
    assert session.query(InterviewTurn).count() == 2

    session.delete(interview)
    session.commit()

    assert session.query(InterviewTurn).count() == 0


def test_turn_stores_rubric_scores_as_json(session: Session) -> None:
    interview = InterviewSession()
    turn = InterviewTurn(
        question="Q",
        answer="A",
        scores_json={"structure": 4, "specificity": 3, "star_adherence": 5},
        feedback="Add a measurable result.",
    )
    interview.turns = [turn]
    session.add(interview)
    session.commit()

    assert session.get(InterviewTurn, turn.id).scores_json["star_adherence"] == 5


def test_deleting_a_jd_keeps_its_interview_history(session: Session) -> None:
    """SET NULL, not CASCADE — practice history outlives the JD it came from."""
    jd = JobDescription(title="Junior Dev", raw_text="...")
    session.add(jd)
    session.commit()

    interview = InterviewSession(jd_id=jd.id)
    session.add(interview)
    session.commit()

    session.delete(jd)
    session.commit()
    session.expire_all()

    survivor = session.get(InterviewSession, interview.id)
    assert survivor is not None
    assert survivor.jd_id is None


def test_roadmap_items_cascade_and_sort_by_position(session: Session) -> None:
    plan = RoadmapPlan(target_role="Backend Developer", plan_json={"summary": "..."})
    plan.items = [
        RoadmapItem(
            horizon=RoadmapHorizon.THREE_MONTH, skill="Docker", action="Build an image", position=2
        ),
        RoadmapItem(
            horizon=RoadmapHorizon.NOW, skill="pytest", action="Test one module", position=1
        ),
    ]
    session.add(plan)
    session.commit()
    session.expire_all()

    stored = session.get(RoadmapPlan, plan.id)
    assert [item.skill for item in stored.items] == ["pytest", "Docker"]

    session.delete(stored)
    session.commit()
    assert session.query(RoadmapItem).count() == 0


def test_outreach_drafts_cascade_from_contact(session: Session) -> None:
    contact = Contact(name="Priya Nair", role="Engineering Manager", company="TechNova")
    contact.drafts = [
        OutreachDraft(
            purpose="Referral request",
            platform=OutreachPlatform.LINKEDIN_NOTE,
            variant_no=1,
            text="Hi Priya, ...",
        ),
        OutreachDraft(
            purpose="Referral request",
            platform=OutreachPlatform.EMAIL,
            variant_no=2,
            text="Dear Priya, ...",
            status=OutreachStatus.SENT,
        ),
    ]
    session.add(contact)
    session.commit()

    assert session.query(OutreachDraft).count() == 2
    assert session.get(OutreachDraft, contact.drafts[0].id).status == OutreachStatus.DRAFT

    session.delete(contact)
    session.commit()
    assert session.query(OutreachDraft).count() == 0


def test_enum_columns_reject_unknown_values(session: Session) -> None:
    """Stored as VARCHAR with a CHECK constraint, since SQLite has no ENUM."""
    session.add(InterviewSession(mode="telepathy"))
    with pytest.raises((StatementError, IntegrityError)):
        session.commit()


def test_enums_persist_lowercase_values_not_member_names(session: Session) -> None:
    """SQLAlchemy stores the member *name* by default, which would write "TEXT".

    The specification says mode[text|voice] and status[draft|sent|replied], so
    `enum_column` overrides that with values_callable. This asserts on the raw
    stored string, bypassing the ORM's type conversion.
    """
    interview = InterviewSession(mode=InterviewMode.VOICE)
    contact = Contact(name="Priya Nair")
    contact.drafts = [
        OutreachDraft(
            purpose="Referral",
            platform=OutreachPlatform.LINKEDIN_NOTE,
            text="Hi",
            status=OutreachStatus.REPLIED,
        )
    ]
    session.add_all([interview, contact])
    session.commit()

    raw_mode = session.execute(text("SELECT mode FROM interview_sessions")).scalar_one()
    raw_platform, raw_status = session.execute(
        text("SELECT platform, status FROM outreach_drafts")
    ).one()

    assert raw_mode == "voice"
    assert raw_platform == "linkedin_note"
    assert raw_status == "replied"


# --------------------------------------------------------------------------- #
# Vector store
# --------------------------------------------------------------------------- #


def test_vector_round_trip_and_nearest_neighbour(session: Session) -> None:
    dim = get_settings().EMBED_DIM

    target = [0.0] * dim
    target[0] = 1.0
    far = [0.0] * dim
    far[dim - 1] = 1.0

    vector_store.add_chunk(
        session,
        source_type=SourceType.RESUME,
        source_id=1,
        chunk_index=0,
        chunk_text="Built a Flask app with MySQL",
        embedding=target,
    )
    vector_store.add_chunk(
        session,
        source_type=SourceType.RESUME,
        source_id=1,
        chunk_index=1,
        chunk_text="Unrelated content",
        embedding=far,
    )
    session.commit()

    results = vector_store.search(session, target, k=2)

    assert len(results) == 2
    assert results[0][0].chunk_text == "Built a Flask app with MySQL"
    assert results[0][1] < results[1][1]  # closest first


def test_search_can_filter_by_source(session: Session) -> None:
    vector_store.add_chunk(
        session,
        source_type=SourceType.RESUME,
        source_id=1,
        chunk_index=0,
        chunk_text="from the resume",
        embedding=make_vector(0.1),
    )
    vector_store.add_chunk(
        session,
        source_type=SourceType.JD,
        source_id=1,
        chunk_index=0,
        chunk_text="from the job description",
        embedding=make_vector(0.1),
    )
    session.commit()

    results = vector_store.search(session, make_vector(0.1), k=5, source_type=SourceType.JD)

    assert [chunk.chunk_text for chunk, _ in results] == ["from the job description"]


def test_wrong_dimension_vector_is_rejected(session: Session) -> None:
    """Catches an embedding-model swap early, with a readable message."""
    with pytest.raises(ValueError, match="768-dimension"):
        vector_store.add_chunk(
            session,
            source_type=SourceType.RESUME,
            source_id=1,
            chunk_index=0,
            chunk_text="too short",
            embedding=[0.1, 0.2, 0.3],
        )


def test_delete_for_source_removes_chunks_and_vectors(session: Session) -> None:
    """No FK reaches into a virtual table, so vectors must be deleted explicitly."""
    for index in range(3):
        vector_store.add_chunk(
            session,
            source_type=SourceType.RESUME,
            source_id=7,
            chunk_index=index,
            chunk_text=f"chunk {index}",
            embedding=make_vector(0.1),
        )
    session.commit()

    removed = vector_store.delete_for_source(session, SourceType.RESUME, 7)
    session.commit()

    assert removed == 3
    assert session.query(EmbeddingChunk).count() == 0
    remaining = session.execute(text(f"SELECT COUNT(*) FROM {VEC_TABLE}")).scalar_one()
    assert remaining == 0
