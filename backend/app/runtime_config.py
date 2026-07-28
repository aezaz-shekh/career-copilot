"""Runtime-overridable settings that outlive a single process.

`config.Settings` is loaded once from the environment and treated as immutable.
A few values, though, need to change while the app is running and persist across
restarts — chiefly the active chat model, which the Settings page lets the user
switch between installed Ollama models (Prompt 4.1). Those live in a small JSON
file next to the database, so no schema or migration is involved.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _path() -> Path:
    """Location of the runtime-overrides file (beside the SQLite database)."""
    return get_settings().DB_PATH.parent / "runtime_settings.json"


def _read() -> dict:
    path = _path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("Ignoring unreadable runtime settings at %s: %s", path, exc)
        return {}


def _write(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_active_chat_model() -> str:
    """The chat model in effect now: a user override, else the configured default."""
    return _read().get("chat_model") or get_settings().CHAT_MODEL


def set_active_chat_model(model: str) -> None:
    """Persist a new active chat model, overriding the configured default."""
    data = _read()
    data["chat_model"] = model
    _write(data)
    logger.info("Active chat model set to %s", model)
