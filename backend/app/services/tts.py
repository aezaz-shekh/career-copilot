"""Text-to-speech via Piper, invoked as a subprocess (Phase 2a).

Piper is a fast local neural TTS binary. We pipe the text in on stdin and have it
write a WAV file, which we read into memory and return, deleting the temp file.
No audio is persisted (SOW Section 6.4).

Optional, like STT: if the binary or voice model is missing, `tts_available()`
returns False and the UI simply reads questions on screen instead of aloud.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class TtsError(RuntimeError):
    """Speech synthesis failed, with a user-facing hint."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class VoiceUnavailableError(TtsError):
    """Piper is not installed, so text-to-speech cannot run."""


def _resolve_binary(path: Path) -> str | None:
    if path.is_file():
        return str(path)
    return shutil.which(path.name)


def tts_available() -> bool:
    """True if voice is enabled and both the Piper binary and voice model exist."""
    settings = get_settings()
    if not settings.VOICE_ENABLED:
        return False
    return _resolve_binary(settings.PIPER_BIN) is not None and settings.PIPER_VOICE.is_file()


def synthesize(text: str) -> bytes:
    """Render `text` to spoken WAV audio and return the bytes.

    Raises:
        VoiceUnavailableError: Piper or its voice model is not installed.
        TtsError: Piper ran but failed or timed out.
    """
    settings = get_settings()
    binary = _resolve_binary(settings.PIPER_BIN)
    if binary is None or not settings.PIPER_VOICE.is_file():
        raise VoiceUnavailableError(
            "Piper is not installed",
            hint="Voice playback needs Piper. See docs/voice-setup.md, or read questions onscreen.",
        )

    text = text.strip()
    if not text:
        raise TtsError("Nothing to speak", hint="The text was empty.")

    settings.ensure_dirs()
    out_path = settings.AUDIO_TMP_DIR / f"tts_{uuid.uuid4().hex}.wav"

    command = [binary, "-m", str(settings.PIPER_VOICE), "-f", str(out_path)]

    try:
        result = subprocess.run(  # noqa: S603 - args are configured paths, not user input
            command,
            input=text,
            capture_output=True,
            text=True,
            timeout=settings.TTS_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning("piper exited %d: %s", result.returncode, result.stderr[-500:])
            raise TtsError(
                "Speech synthesis failed", hint="Try again, or read the question on screen."
            )

        if not out_path.is_file():
            raise TtsError("Piper produced no audio", hint="Check the Piper voice model path.")
        audio = out_path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise TtsError(
            f"Speech synthesis timed out after {settings.TTS_TIMEOUT:.0f}s",
            hint="The text may be very long. Try a shorter passage.",
        ) from exc
    except OSError as exc:
        raise TtsError(
            f"Could not run Piper: {exc}",
            hint="Check the Piper binary path in your .env, or read questions on screen.",
        ) from exc
    finally:
        out_path.unlink(missing_ok=True)  # no audio persists

    logger.info("Synthesised %d bytes of audio for %d characters", len(audio), len(text))
    return audio
