"""Retrieval-Augmented Generation pipeline (SOW Section 6.2).

WHY THIS EXISTS — how retrieval keeps a 3B model specific
---------------------------------------------------------
A 3B model has a small amount of world knowledge and a limited context window,
and on this hardware every token it has to read costs latency. If we pasted an
entire resume and an entire job description into the prompt and asked for a
critique, three things would go wrong:

  1. The prompt would be long, so generation would be slow and the model would
     "lose" details in the middle of a big blob of text.
  2. The model would fall back on generic advice ("add measurable achievements")
     because nothing in the prompt forced it to engage with THIS person's actual
     bullet points.
  3. It might hallucinate — inventing experience the candidate does not have.

RAG fixes this by changing WHAT goes into the prompt. Instead of the whole
document, we:

  - split each document into small chunks once, at save time, and store an
    embedding (a semantic fingerprint) for each chunk;
  - at generation time, embed the *question* ("what backend skills does this
    candidate show?") and retrieve only the handful of chunks whose meaning is
    closest to it;
  - inject just those chunks into the prompt.

The model then reasons over a short, highly relevant slice of the candidate's
real text. Its answer is forced to be concrete because the concrete evidence is
right there in front of it, and generation is fast because the prompt is small.
This is what the SOW means by "closing most of the quality gap to cloud frontier
models for these narrow tasks" — we are not making the model smarter, we are
making sure it only ever looks at the text that matters.

PERFORMANCE NOTE (8 GB machine)
-------------------------------
Embedding and chat use two different Ollama models. On 8 GB RAM loading one
evicts the other, and reloading a model costs ~15 s. So embedding happens in a
single batch at *save* time (`index_source`), never once per request. At
retrieval time only ONE embedding call is made — for the query — which keeps the
chat model resident for the generation that follows.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.client import OllamaClient
from app.models.base import SourceType
from app.services import vector_store

logger = logging.getLogger(__name__)

# Roughly four characters per token for English prose. Good enough to size
# chunks without pulling in a real tokeniser, which would be one more dependency
# and more model-loading on a memory-constrained machine.
CHARS_PER_TOKEN = 4

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WHITESPACE = re.compile(r"[ \t]+")


@dataclass
class Chunk:
    """One unit of text to embed and later retrieve."""

    index: int
    text: str


@dataclass
class RetrievedChunk:
    """A chunk returned by retrieval, with its provenance and score."""

    text: str
    source_type: SourceType
    source_id: int
    chunk_index: int
    distance: float  # cosine distance in [0, 2]; smaller is more similar

    @property
    def similarity(self) -> float:
        """Cosine similarity in [-1, 1], the friendlier number to read."""
        return round(1.0 - self.distance, 4)


def _normalise_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs but keep paragraph breaks meaningful."""
    text = _WHITESPACE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _split_sentences(text: str) -> list[str]:
    """Split into sentence-ish units on terminal punctuation and blank lines."""
    parts = _SENTENCE_SPLIT.split(text)
    return [part.strip() for part in parts if part and part.strip()]


def chunk_text(text: str, target_tokens: int = 250, overlap: int = 40) -> list[Chunk]:
    """Split text into overlapping, sentence-aware chunks.

    Sentence-aware: we never cut in the middle of a sentence, because a half
    sentence embeds to a muddled point in vector space and retrieves poorly. We
    add whole sentences to the current chunk until it reaches ~`target_tokens`,
    then start a new one.

    Overlap: consecutive chunks share the last ~`overlap` tokens of the previous
    one. This stops a fact that straddles a boundary (a bullet whose metric is in
    the next sentence) from being lost to whichever chunk happens to split it.

    Args:
        text: The source text.
        target_tokens: Approximate size of each chunk, in tokens.
        overlap: Approximate tokens of overlap between neighbours.

    Returns:
        Chunks in document order, each with a stable index.
    """
    cleaned = _normalise_whitespace(text)
    if not cleaned:
        return []

    target_chars = target_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN

    sentences = _split_sentences(cleaned)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunk_body = " ".join(current).strip()
        chunks.append(Chunk(index=len(chunks), text=chunk_body))

        # Seed the next chunk with the tail of this one, so context carries over.
        if overlap_chars <= 0:
            current, current_len = [], 0
            return
        carry: list[str] = []
        carry_len = 0
        for sentence in reversed(current):
            carry.insert(0, sentence)
            carry_len += len(sentence) + 1
            if carry_len >= overlap_chars:
                break
        current = carry
        current_len = carry_len

    for sentence in sentences:
        # A single sentence longer than the target becomes its own chunk rather
        # than being hard-cut mid-word.
        if len(sentence) > target_chars and current:
            flush()
        current.append(sentence)
        current_len += len(sentence) + 1
        if current_len >= target_chars:
            flush()

    # Append the trailing remainder, unless it is a pure duplicate of the
    # overlap already emitted (which happens when the last flush consumed
    # everything and the carry equals the final chunk).
    flush_final = " ".join(current).strip()
    if flush_final and (not chunks or not chunks[-1].text.endswith(flush_final)):
        chunks.append(Chunk(index=len(chunks), text=flush_final))

    return chunks


async def index_source(
    session: Session,
    source_type: SourceType,
    source_id: int,
    text: str,
    *,
    client: OllamaClient | None = None,
) -> int:
    """Chunk `text`, embed each chunk locally, and store it for retrieval.

    Idempotent per source: any existing chunks for (source_type, source_id) are
    removed first, so re-saving a resume re-indexes it cleanly rather than
    accumulating stale duplicates.

    All embedding happens here, in one batch, at save time — never per request —
    so the chat model is not evicted from RAM during a later generation.

    Returns:
        The number of chunks stored.
    """
    client = client or OllamaClient()

    chunks = chunk_text(text)
    if not chunks:
        logger.info("Nothing to index for %s:%s (empty text)", source_type.value, source_id)
        vector_store.delete_for_source(session, source_type, source_id)
        session.commit()
        return 0

    # Replace rather than append, so this is safe to call on every save.
    vector_store.delete_for_source(session, source_type, source_id)

    for chunk in chunks:
        embedding = await client.embed(chunk.text)
        vector_store.add_chunk(
            session,
            source_type=source_type,
            source_id=source_id,
            chunk_index=chunk.index,
            chunk_text=chunk.text,
            embedding=embedding,
        )

    session.commit()
    logger.info("Indexed %s:%s into %d chunks", source_type.value, source_id, len(chunks))
    return len(chunks)


async def retrieve(
    session: Session,
    query: str,
    *,
    source_ids: dict[SourceType, int] | None = None,
    top_k: int = 6,
    client: OllamaClient | None = None,
) -> list[RetrievedChunk]:
    """Return the `top_k` chunks most semantically similar to `query`.

    Args:
        query: The natural-language question or task the chunks should support.
        source_ids: Optional {SourceType: id} filter, e.g.
            {RESUME: 3, JD: 3} to retrieve only from this resume and this JD and
            nothing left over from earlier uploads. Omit to search everything.
        top_k: How many chunks to inject into the downstream prompt.

    Returns:
        Chunks ordered most-similar first. Only ONE embedding call is made here
        (for the query), which keeps the chat model resident for generation.
    """
    settings = get_settings()
    client = client or OllamaClient()

    query_embedding = await client.embed(query, model=settings.EMBED_MODEL)

    scoped = _restrict_to_sources(source_ids) if source_ids else [(None, None)]

    results: list[RetrievedChunk] = []
    for source_type, source_id in scoped:
        hits = vector_store.search(
            session,
            query_embedding,
            k=top_k,
            source_type=source_type,
            source_id=source_id,
        )
        for chunk, distance in hits:
            results.append(
                RetrievedChunk(
                    text=chunk.chunk_text,
                    source_type=chunk.source_type,
                    source_id=chunk.source_id,
                    chunk_index=chunk.chunk_index,
                    distance=distance,
                )
            )

    results.sort(key=lambda item: item.distance)
    return results[:top_k]


def _restrict_to_sources(
    source_ids: dict[SourceType, int],
) -> list[tuple[SourceType, int]]:
    """Expand a {type: id} filter into (type, id) pairs to search separately.

    Searching each source in its own KNN call and then merging keeps the result
    balanced — otherwise a long JD could crowd out every chunk of a short resume,
    even when both are relevant to the query.
    """
    return list(source_ids.items())


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for injection into a prompt.

    Each chunk is labelled with its source so a downstream prompt can tell resume
    evidence from job-description evidence — the distinction a critique depends on.
    """
    lines: list[str] = []
    for chunk in chunks:
        label = "RESUME" if chunk.source_type == SourceType.RESUME else "JOB DESCRIPTION"
        lines.append(f"[{label}] {chunk.text}")
    return "\n\n".join(lines)
