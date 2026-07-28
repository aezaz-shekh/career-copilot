"""Schemas for the development/diagnostic endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EchoRequest(BaseModel):
    """A single prompt to send straight to the local model."""

    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Prompt text to send to the model",
        examples=["Say hello in one short sentence."],
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Sampling temperature; defaults to TEMPERATURE_CREATIVE",
    )
    model: str | None = Field(
        default=None, description="Override the configured chat model for this call"
    )
    num_predict: int | None = Field(
        default=None,
        ge=1,
        le=4096,
        description="Cap the number of tokens generated, to keep replies snappy",
    )


class RetrievedChunkOut(BaseModel):
    """One retrieved chunk, as shown by the rag-test diagnostic endpoint."""

    source_type: str = Field(description="resume or jd")
    source_id: int
    chunk_index: int
    similarity: float = Field(description="Cosine similarity in [-1, 1]; higher is closer")
    distance: float = Field(description="Cosine distance in [0, 2]; lower is closer")
    text: str


class RagTestResponse(BaseModel):
    """Result of GET /api/dev/rag-test."""

    query: str
    indexed_chunks: int = Field(description="Total chunks currently in the vector store")
    returned: int
    results: list[RetrievedChunkOut]
