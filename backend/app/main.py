"""FastAPI application entry point for AI Career Co-Pilot.

Run from the `backend/` directory:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Interactive API docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import init_db
from app.llm.client import OllamaError
from app.routers import (
    dev,
    health,
    interviews,
    jds,
    outreach,
    resumes,
    review,
    roadmap,
    setup,
    stats,
    voice,
)
from app.routers import (
    settings as settings_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare local storage on startup and log the active configuration."""
    settings = get_settings()
    settings.ensure_dirs()
    logger.info("%s v%s starting", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Chat model: %s | Embed model: %s", settings.CHAT_MODEL, settings.EMBED_MODEL)
    logger.info("Ollama URL: %s", settings.OLLAMA_URL)
    logger.info("Database:   %s", settings.DB_PATH)

    # Idempotent: creates any missing table, touches nothing that exists.
    init_db()
    yield
    logger.info("Shutting down")


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Privacy-first career assistant. All inference runs locally via Ollama; "
        "no data ever leaves this machine."
    ),
    lifespan=lifespan,
)

# The frontend dev server runs on a different port, so it needs CORS.
# Only loopback origins are allowed — the app is never reachable off-machine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OllamaError)
async def ollama_error_handler(request: Request, exc: OllamaError) -> JSONResponse:
    """Turn any uncaught Ollama failure into the same {message, hint} shape the
    frontend already understands, so a down/missing model never leaks a stack
    trace (SOW Section 7). Registering the base class also catches
    OllamaDownError, ModelMissingError, and GenerationError (timeouts).
    """
    logger.warning("%s: %s", type(exc).__name__, exc.message)
    return JSONResponse(
        status_code=503,
        content={"detail": {"message": exc.message, "hint": exc.hint}},
    )


app.include_router(health.router)
app.include_router(dev.router)
app.include_router(resumes.router)
app.include_router(jds.router)
app.include_router(review.router)
app.include_router(interviews.router)
app.include_router(roadmap.router)
app.include_router(outreach.router)
app.include_router(voice.router)
app.include_router(setup.router)
app.include_router(settings_router.router)
app.include_router(stats.router)


@app.get("/", tags=["system"], summary="Service banner")
async def root() -> dict[str, str]:
    """Confirm the API is alive and point to the docs."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
