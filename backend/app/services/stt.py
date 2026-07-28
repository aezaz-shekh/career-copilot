"""Speech-to-text via whisper.cpp, invoked as a subprocess (Phase 2a).

whisper.cpp is a local C++ binary — no Python model, no cloud. We shell out to
it with the `tiny.en` model (the smallest tier, chosen for 8 GB CPU-only
hardware per SOW Section 11) and read the transcript from stdout.

PRIVACY (SOW Section 6.4): the audio file is deleted immediately after
transcription, in a `finally` block, so it is removed even if whisper fails.
Only the transcript text ever leaves this module.

Voice is optional. If the binary or model is missing, `stt_available()` returns
False and the app stays in text-only mode rather than erroring.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class SttError(RuntimeError):
    """Transcription failed, with a user-facing hint."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class VoiceUnavailableError(SttError):
    """whisper.cpp is not installed, so speech-to-text cannot run."""


def _resolve_binary(path: Path) -> str | None:
    """Return a runnable command for `path`, or None if it cannot be found.

    Accepts either a real file path or a bare command name resolved on PATH, so
    a user who put whisper-cli on PATH does not have to set an absolute path.
    """
    if path.is_file():
        return str(path)
    found = shutil.which(path.name)
    return found


def stt_available() -> bool:
    """True if both the whisper binary and the model are present."""
    settings = get_settings()
    return _resolve_binary(settings.WHISPER_BIN) is not None and settings.WHISPER_MODEL.is_file()


def _parse_output(stdout: str) -> str:
    """Join whisper-cli's plain-text output lines into one transcript.

    With `-nt` (no timestamps) whisper-cli prints the transcription as plain
    lines on stdout; logging goes to stderr and is not captured here.
    """
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return " ".join(lines).strip()


def transcribe(wav_path: Path) -> str:
    """Transcribe a 16 kHz mono WAV file and delete it afterwards.

    Args:
        wav_path: Path to the WAV file to transcribe. Always deleted before this
            function returns (the privacy guarantee).

    Raises:
        VoiceUnavailableError: whisper.cpp or its model is not installed.
        SttError: whisper ran but failed or timed out.
    """
    settings = get_settings()
    binary = _resolve_binary(settings.WHISPER_BIN)
    if binary is None or not settings.WHISPER_MODEL.is_file():
        wav_path.unlink(missing_ok=True)
        raise VoiceUnavailableError(
            "whisper.cpp is not installed",
            hint="Voice mode needs whisper.cpp. See docs/voice-setup.md, or use text mode.",
        )

    # -nt: no timestamps, plain text. -l en: English. Output goes to stdout.
    command = [
        binary,
        "-m",
        str(settings.WHISPER_MODEL),
        "-f",
        str(wav_path),
        "-nt",
        "-l",
        "en",
    ]

    try:
        result = subprocess.run(  # noqa: S603 - args are configured paths, not user input
            command,
            capture_output=True,
            text=True,
            timeout=settings.STT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise SttError(
            f"Transcription timed out after {settings.STT_TIMEOUT:.0f}s",
            hint="The recording may be too long. Keep spoken answers under a minute or two.",
        ) from exc
    except OSError as exc:
        raise SttError(
            f"Could not run whisper.cpp: {exc}",
            hint="Check the whisper binary path in your .env, or use text mode.",
        ) from exc
    finally:
        # Privacy: the audio never persists, whatever happened above.
        wav_path.unlink(missing_ok=True)

    if result.returncode != 0:
        logger.warning("whisper-cli exited %d: %s", result.returncode, result.stderr[-500:])
        raise SttError(
            "Transcription failed",
            hint="The audio may be empty or corrupt. Try recording again, or use text mode.",
        )

    transcript = _parse_output(result.stdout)
    logger.info("Transcribed %d characters", len(transcript))
    return transcript
