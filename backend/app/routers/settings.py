"""Settings endpoints (Phase 4, Prompt 4.1).

Lets the user see where their data lives, switch the active chat model to any
installed Ollama model, and delete all their data behind a typed confirmation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import runtime_config
from app.config import get_settings
from app.db import get_session, reset_all_data
from app.llm.client import find_missing_models, list_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ModelSelection(BaseModel):
    model: str = Field(min_length=1)


class DataDeletion(BaseModel):
    confirm: str = Field(description="Must equal 'DELETE' to proceed")


@router.get("", summary="Current settings and where data lives")
async def read_settings() -> dict:
    settings = get_settings()
    db_path = settings.DB_PATH
    installed: list[str] = []
    try:
        installed = await list_models()
    except Exception:  # noqa: BLE001 - a down Ollama just means an empty list here
        installed = []

    return {
        "chat_model": runtime_config.get_active_chat_model(),
        "default_chat_model": settings.CHAT_MODEL,
        "question_model": settings.QUESTION_MODEL,
        "embed_model": settings.EMBED_MODEL,
        "installed_models": installed,
        "data_path": str(db_path),
        "data_bytes": db_path.stat().st_size if db_path.is_file() else 0,
    }


@router.put("/model", summary="Switch the active chat model")
async def set_model(selection: ModelSelection) -> dict:
    """Point the app at a different installed model. Rejects one that isn't pulled."""
    installed = await list_models()  # OllamaError -> global 503 handler
    if find_missing_models([selection.model], installed):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Model '{selection.model}' is not installed",
                "hint": f"Download it first with: ollama pull {selection.model}",
            },
        )
    runtime_config.set_active_chat_model(selection.model)
    return {"chat_model": selection.model}


@router.delete("/data", summary="Delete ALL data (typed confirmation required)")
def delete_all_data(body: DataDeletion, session: Session = Depends(get_session)) -> dict:
    """Wipe every row from the database after the user types DELETE.

    Schema and app stay intact — only the user's content is removed. Temp audio
    (which should already be gone) is swept too, for good measure.
    """
    if body.confirm != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Confirmation text did not match.",
                "hint": "Type DELETE (in capitals) to confirm.",
            },
        )

    tables_cleared = reset_all_data(session.get_bind())

    audio_dir = get_settings().AUDIO_TMP_DIR
    swept = 0
    if audio_dir.is_dir():
        for leftover in audio_dir.glob("*"):
            try:
                leftover.unlink()
                swept += 1
            except OSError:
                pass

    logger.info("Deleted all data: %d tables cleared, %d temp files swept", tables_cleared, swept)
    return {"deleted": True, "tables_cleared": tables_cleared, "temp_files_removed": swept}
