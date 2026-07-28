"""Tests for the RAG pipeline: chunking, indexing, and retrieval.

Chunking is a pure function and is tested directly. Indexing and retrieval use a
deterministic fake embedder (keyword-based vectors) via httpx.MockTransport, so
the real pipeline code runs end to end without Ollama and retrieval order is
predictable.
"""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import VEC_TABLE, create_db_engine, init_db
from app.llm import rag
from app.llm.client import OllamaClient
from app.models.base import SourceType
from app.services import vector_store

DIM = get_settings().EMBED_DIM

# A tiny "topic" vocabulary. Each keyword owns one dimension; a text's embedding
# lights up the dimensions of the keywords it contains. Cosine similarity then
# ranks texts by shared vocabulary — a crude but fully deterministic stand-in
# for a real embedding model.
TOPICS = ["python", "sql", "docker", "react", "flask", "testing", "aws", "leadership"]


def fake_embedding(content: str) -> list[float]:
    lowered = content.lower()
    vec = [0.0] * DIM
    for i, word in enumerate(TOPICS):
        if word in lowered:
            vec[i] = 1.0
    # A small constant in a spare dimension avoids an all-zero vector (undefined
    # cosine) for text that mentions none of the keywords.
    vec[DIM - 1] = 0.05
    return vec


def embedding_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        payload = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [fake_embedding(payload["input"])]})

    return httpx.MockTransport(handler)


def fake_client() -> OllamaClient:
    return OllamaClient(transport=embedding_transport())


@pytest.fixture
def session(tmp_path) -> Session:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag.db'}")
    init_db(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


# --------------------------------------------------------------------------- #
# chunk_text  (pure function)
# --------------------------------------------------------------------------- #


def test_chunking_short_text_is_one_chunk() -> None:
    chunks = rag.chunk_text("A short resume line about Python and SQL.")

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert "Python" in chunks[0].text


def test_chunking_long_text_splits_into_several() -> None:
    sentence = "This candidate built a Flask API backed by a normalised MySQL schema. "
    chunks = rag.chunk_text(sentence * 40, target_tokens=60, overlap=10)

    assert len(chunks) > 3
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunking_is_sentence_aware() -> None:
    """No chunk should begin or end mid-sentence (i.e. mid-word)."""
    text_body = (
        "Built a library management system in Flask. "
        "Designed a MySQL schema with seven tables. "
        "Reduced search time to under five seconds. "
        "Wrote SQL for the monthly reporting module. "
    ) * 6
    chunks = rag.chunk_text(text_body, target_tokens=40, overlap=8)

    for chunk in chunks:
        assert chunk.text[0].isupper() or chunk.text[0].isdigit()
        assert chunk.text.rstrip()[-1] in ".!?"


def test_chunking_overlap_shares_content_between_neighbours() -> None:
    sentences = [f"Sentence number {i} about backend engineering work." for i in range(30)]
    chunks = rag.chunk_text(" ".join(sentences), target_tokens=40, overlap=20)

    # With overlap, some sentence text recurs across a boundary.
    joined = [c.text for c in chunks]
    overlaps = sum(
        1
        for a, b in zip(joined, joined[1:], strict=False)
        if any(word in b for word in a.split(".")[-2:] if word.strip())
    )
    assert overlaps >= 1


def test_chunking_empty_text_returns_nothing() -> None:
    assert rag.chunk_text("") == []
    assert rag.chunk_text("   \n\n  ") == []


def test_chunking_collapses_pdf_whitespace_noise() -> None:
    messy = "Python     developer.\n\n\n   Built   APIs    with\tFastAPI."
    chunks = rag.chunk_text(messy)

    assert "     " not in chunks[0].text
    assert "\t" not in chunks[0].text


# --------------------------------------------------------------------------- #
# index_source + retrieve
# --------------------------------------------------------------------------- #


async def test_index_source_stores_chunks_and_vectors(session: Session) -> None:
    count = await rag.index_source(
        session,
        SourceType.RESUME,
        1,
        "Built a Flask API. Wrote SQL queries. Used Python throughout the project.",
        client=fake_client(),
    )

    assert count >= 1
    stored = session.query(vector_store.EmbeddingChunk).count()
    assert stored == count
    vectors = session.execute(text(f"SELECT COUNT(*) FROM {VEC_TABLE}")).scalar_one()
    assert vectors == count


async def test_reindexing_replaces_rather_than_appends(session: Session) -> None:
    await rag.index_source(session, SourceType.RESUME, 1, "Python and SQL.", client=fake_client())
    first = session.query(vector_store.EmbeddingChunk).count()

    await rag.index_source(session, SourceType.RESUME, 1, "Docker and AWS.", client=fake_client())
    second = session.query(vector_store.EmbeddingChunk).count()

    assert second == first  # replaced, not doubled
    remaining = session.query(vector_store.EmbeddingChunk).all()
    assert all("Docker" in c.chunk_text or "AWS" in c.chunk_text for c in remaining)


async def test_retrieve_ranks_relevant_chunks_first(session: Session) -> None:
    await rag.index_source(
        session,
        SourceType.RESUME,
        1,
        "I led a team using leadership skills. "
        "I built REST APIs with Python and Flask. "
        "I deployed containers with Docker on AWS.",
        client=fake_client(),
    )

    results = await rag.retrieve(session, "python flask backend", top_k=3, client=fake_client())

    assert results
    # The Python/Flask chunk must rank above the leadership one.
    assert "Python" in results[0].text or "Flask" in results[0].text
    assert results[0].similarity >= results[-1].similarity


async def test_retrieve_can_scope_to_one_source(session: Session) -> None:
    await rag.index_source(
        session, SourceType.RESUME, 1, "Python developer with SQL experience.", client=fake_client()
    )
    await rag.index_source(
        session, SourceType.JD, 1, "We need Python and Docker skills.", client=fake_client()
    )

    only_jd = await rag.retrieve(
        session, "python", source_ids={SourceType.JD: 1}, top_k=5, client=fake_client()
    )

    assert only_jd
    assert all(chunk.source_type == SourceType.JD for chunk in only_jd)


async def test_retrieve_returns_similarity_scores(session: Session) -> None:
    await rag.index_source(
        session, SourceType.RESUME, 1, "Python and SQL and Docker.", client=fake_client()
    )

    results = await rag.retrieve(session, "python sql docker", top_k=1, client=fake_client())

    # Identical keyword sets -> cosine similarity close to 1.
    assert results[0].similarity > 0.9
    assert 0.0 <= results[0].distance <= 2.0


async def test_retrieve_on_empty_store_returns_nothing(session: Session) -> None:
    assert await rag.retrieve(session, "anything", client=fake_client()) == []


def test_context_block_labels_each_source(session: Session) -> None:
    chunks = [
        rag.RetrievedChunk("Python developer", SourceType.RESUME, 1, 0, 0.1),
        rag.RetrievedChunk("Needs Docker", SourceType.JD, 1, 0, 0.2),
    ]

    block = rag.build_context_block(chunks)

    assert "[RESUME] Python developer" in block
    assert "[JOB DESCRIPTION] Needs Docker" in block


# --------------------------------------------------------------------------- #
# Cosine metric on the real table
# --------------------------------------------------------------------------- #


def test_vector_table_uses_cosine_metric(session: Session) -> None:
    """The table must be created with distance_metric=cosine, not default L2."""
    sql = session.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": VEC_TABLE},
    ).scalar_one()
    assert "cosine" in sql.lower()


def test_cosine_ranking_ignores_magnitude(session: Session) -> None:
    """Cosine must rank by direction, not length — the reason we chose it.

    A short vector and a long vector pointing the same way must be judged more
    similar than two vectors of equal length pointing differently.
    """
    same_direction_long = [2.0] + [0.0] * (DIM - 1)
    same_direction_short = [0.5] + [0.0] * (DIM - 1)
    other_direction = [0.0, 1.0] + [0.0] * (DIM - 2)

    vector_store.add_chunk(
        session,
        source_type=SourceType.RESUME,
        source_id=1,
        chunk_index=0,
        chunk_text="long same direction",
        embedding=same_direction_long,
    )
    vector_store.add_chunk(
        session,
        source_type=SourceType.RESUME,
        source_id=1,
        chunk_index=1,
        chunk_text="other direction",
        embedding=other_direction,
    )
    session.commit()

    hits = vector_store.search(session, same_direction_short, k=2)

    assert hits[0][0].chunk_text == "long same direction"
    assert hits[0][1] < hits[1][1]
