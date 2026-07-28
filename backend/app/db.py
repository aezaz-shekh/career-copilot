"""Database engine, session factory, and schema initialisation.

One SQLite file holds everything (SOW Section 5: "single portable file"), with
the sqlite-vec extension loaded on every connection so vector search runs inside
the same database — no separate vector service to install or run.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from functools import lru_cache

import sqlite_vec
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  -- registers every table on Base.metadata
from app.config import get_settings
from app.models.base import Base

logger = logging.getLogger(__name__)

VEC_TABLE = "vec_embedding_chunks"


def _configure_connection(dbapi_connection: sqlite3.Connection, _record: object) -> None:
    """Prepare each new SQLite connection.

    Runs on every connect because SQLite pragmas and loaded extensions are
    per-connection, not per-database.
    """
    # SQLite ships with foreign keys DISABLED. Without this, every ON DELETE
    # CASCADE in the schema is silently ignored.
    dbapi_connection.execute("PRAGMA foreign_keys=ON")

    # WAL lets the UI read while a write is in flight, so a long embedding
    # insert does not block the page.
    dbapi_connection.execute("PRAGMA journal_mode=WAL")

    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Build an engine with sqlite-vec and the required pragmas wired in.

    Args:
        url: SQLAlchemy URL. Defaults to the configured SQLite file.
        echo: Log every statement — useful when debugging a query.
    """
    settings = get_settings()
    if url is None:
        settings.ensure_dirs()
        url = settings.database_url

    engine = create_engine(url, echo=echo, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _configure_connection)
    return engine


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine (created once, on first use)."""
    return create_db_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that always closes."""
    with get_session_factory()() as session:
        yield session


def create_vec_table(engine: Engine) -> None:
    """Create the sqlite-vec virtual table that stores embedding vectors.

    `float[N]` fixes the vector width at the embedding model's dimensionality —
    768 for nomic-embed-text. Swapping to a model with a different width means
    dropping this table and re-embedding, which is why the dimension is a
    configured value rather than a literal.
    """
    settings = get_settings()

    # distance_metric=cosine makes similarity independent of vector magnitude,
    # which is what we want for text: two passages about the same topic should
    # match on direction (meaning) even if one is longer and its raw embedding
    # larger. nomic-embed-text vectors are not unit-normalised, so the default
    # L2 metric would let length skew relevance. sqlite-vec computes cosine
    # natively, so nothing has to normalise vectors by hand.
    create_sql = (
        f"CREATE VIRTUAL TABLE {VEC_TABLE} USING vec0("
        f"  chunk_id INTEGER PRIMARY KEY,"
        f"  embedding float[{settings.EMBED_DIM}] distance_metric=cosine"
        f")"
    )

    with engine.begin() as connection:
        existing_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": VEC_TABLE},
        ).scalar_one_or_none()

        if existing_sql is None:
            connection.execute(text(create_sql))
            return

        if "cosine" in existing_sql.lower():
            return  # already correct

        # An older table used the default L2 metric. The vector table is not
        # rebuildable from other tables (only it stores the vectors), so only
        # recreate it automatically when it holds no data. Otherwise a real
        # re-embedding migration is needed, and we refuse to drop data silently.
        chunk_count = connection.execute(text("SELECT COUNT(*) FROM embedding_chunks")).scalar_one()
        if chunk_count == 0:
            logger.info("Recreating %s with cosine distance metric (was empty)", VEC_TABLE)
            connection.execute(text(f"DROP TABLE {VEC_TABLE}"))
            connection.execute(text(create_sql))
        else:
            logger.warning(
                "%s uses a non-cosine metric and holds %d rows. Delete the vector "
                "data and re-index to switch to cosine.",
                VEC_TABLE,
                chunk_count,
            )


def ensure_columns(engine: Engine, table: str, columns: dict[str, str]) -> None:
    """Add any missing columns to an existing table (lightweight migration).

    `Base.metadata.create_all` creates missing *tables* but never alters an
    existing one, so a column added to a model after its table was first created
    would be invisible without this. SQLite's ADD COLUMN is safe and idempotent;
    on a fresh database every column already exists and this is a no-op.
    """
    with engine.begin() as connection:
        existing = {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})")).all()}
        for name, ddl in columns.items():
            if name not in existing:
                logger.info("Migrating: adding column %s.%s", table, name)
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(engine: Engine | None = None) -> Engine:
    """Create every table that does not exist yet, and return the engine.

    Safe to call on every startup: `create_all`, the virtual-table statement,
    and the column migrations are all idempotent, so existing data is untouched.
    """
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    create_vec_table(engine)
    # Columns added to models after their table first shipped.
    ensure_columns(engine, "interview_sessions", {"question_bank_json": "JSON"})  # Phase 2.2
    ensure_columns(engine, "outreach_drafts", {"tone": "VARCHAR", "subject": "TEXT"})  # Phase 3a
    logger.info("Database ready: %s", engine.url)
    return engine


def reset_all_data(engine: Engine | None = None) -> int:
    """Delete every row from every table, keeping the schema intact.

    Backs the Settings page's "Delete ALL my data" action (Prompt 4.1). Rows are
    cleared in reverse dependency order so foreign keys are never violated, and
    the sqlite-vec virtual table is emptied too. The tables themselves survive,
    so the app keeps working immediately afterwards. Returns the table count.
    """
    engine = engine or get_engine()
    with engine.begin() as connection:
        connection.execute(text(f"DELETE FROM {VEC_TABLE}"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    logger.info("Reset: cleared all data from %d tables", len(Base.metadata.sorted_tables))
    return len(Base.metadata.sorted_tables)


def vec_version(engine: Engine | None = None) -> str:
    """Return the loaded sqlite-vec version (used by the health endpoint)."""
    engine = engine or get_engine()
    with engine.connect() as connection:
        return connection.execute(text("SELECT vec_version()")).scalar_one()
