"""Loader for versioned prompt templates stored in `prompts/`.

Prompts live in plain text files rather than Python string literals so they can
be versioned and diffed independently of the code (SOW Section 7,
Maintainability: "versioned prompt templates"), and so the Phase 5 evaluation
harness can compare output quality across revisions.

Placeholders use `string.Template` syntax (`$resume_text`), not `str.format`.
The reason is practical: these templates describe JSON, and `str.format` treats
every `{` in a JSON example as a field reference and raises.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from string import Template

from app.config import get_settings

logger = logging.getLogger(__name__)

# Matches "resume_parser_v2.txt" and captures the version number.
_VERSIONED = re.compile(r"^(?P<stem>.+)_v(?P<version>\d+)\.txt$")


class PromptNotFoundError(FileNotFoundError):
    """No template file exists for the requested prompt name."""


def prompts_dir() -> Path:
    return get_settings().PROMPTS_DIR


def resolve_prompt_path(name: str, version: int | None = None) -> Path:
    """Find the file backing a prompt name.

    Accepts a bare name (`"resume_parser"`) and resolves it to the highest
    available version, so calling code never hard-codes a version number and a
    new revision goes live by adding a file. Pass `version` to pin one
    explicitly, which is what the evaluation harness does.
    """
    directory = prompts_dir()

    if version is not None:
        path = directory / f"{name}_v{version}.txt"
        if not path.is_file():
            raise PromptNotFoundError(f"No prompt template at {path}")
        return path

    # An exact filename, for templates that are not versioned.
    exact = directory / f"{name}.txt"

    candidates: list[tuple[int, Path]] = []
    if directory.is_dir():
        for candidate in directory.glob(f"{name}_v*.txt"):
            match = _VERSIONED.match(candidate.name)
            if match and match.group("stem") == name:
                candidates.append((int(match.group("version")), candidate))

    if candidates:
        return max(candidates, key=lambda pair: pair[0])[1]
    if exact.is_file():
        return exact

    raise PromptNotFoundError(
        f"No prompt template named '{name}' in {directory}. Expected {name}_v1.txt or {name}.txt"
    )


@lru_cache(maxsize=64)
def load_prompt(name: str, version: int | None = None) -> str:
    """Return the raw text of a prompt template (cached after first read)."""
    path = resolve_prompt_path(name, version)
    logger.debug("Loaded prompt template %s", path.name)
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, version: int | None = None, **values: object) -> str:
    """Load a template and substitute its placeholders.

    Uses `safe_substitute`, so a stray `$` in user-supplied resume text cannot
    blow up generation with a KeyError.
    """
    template = Template(load_prompt(name, version))
    return template.safe_substitute(**values)
