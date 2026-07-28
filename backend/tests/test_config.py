"""Guardrail tests for configuration.

These encode two hard project constraints so a careless change fails CI rather
than surfacing as a slow app or a privacy hole during the demo.
"""

from __future__ import annotations

from app.config import get_settings


def test_defaults_match_the_specification() -> None:
    settings = get_settings()
    assert settings.CHAT_MODEL == "llama3.2:3b"
    assert settings.EMBED_MODEL == "nomic-embed-text"
    assert settings.TEMPERATURE_SCORING == 0.2
    assert settings.TEMPERATURE_CREATIVE == 0.7


def test_scoring_is_colder_than_creative() -> None:
    """Low temperature for scoring is what keeps rubric scores within +/-1 point."""
    settings = get_settings()
    assert settings.TEMPERATURE_SCORING < settings.TEMPERATURE_CREATIVE


def test_binds_to_loopback_only() -> None:
    """SOW Section 6.4: the app must be unreachable from the network."""
    settings = get_settings()
    assert settings.HOST == "127.0.0.1"
    assert settings.OLLAMA_URL.startswith(("http://127.0.0.1", "http://localhost"))
