"""Voice endpoints: speech-to-text and text-to-speech (Phase 2a).

These wrap the whisper.cpp and Piper subprocesses. Scoring is unchanged — a
transcribed answer is submitted to the existing `/api/interviews/answer`, so
voice and text answers go through exactly the same rubric (SOW Section 4.1).

The blocking subprocesses run in a worker thread so they never stall the async
event loop.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import stt, tts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceStatus(BaseModel):
    stt_available: bool = Field(description="True if whisper.cpp is installed")
    tts_available: bool = Field(description="True if Piper is installed")


class TranscribeResponse(BaseModel):
    transcript: str


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.get("/status", response_model=VoiceStatus, summary="Is voice mode available?")
def voice_status() -> VoiceStatus:
    """Report whether STT and TTS can run, so the UI can offer voice or fall back.

    Always 200 — an uninstalled binary is a reported capability, not an error.
    """
    return VoiceStatus(stt_available=stt.stt_available(), tts_available=tts.tts_available())


@router.post("/transcribe", response_model=TranscribeResponse, summary="Transcribe a WAV recording")
async def transcribe(file: UploadFile = File(...)) -> TranscribeResponse:
    """Transcribe an uploaded 16 kHz mono WAV recording.

    The audio is written to a temp file, transcribed, and deleted immediately
    (the deletion happens inside `stt.transcribe`, even on failure).
    """
    settings = get_settings()
    data = await file.read()

    if len(data) > settings.MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"message": "Recording is too large", "hint": "Keep spoken answers short."},
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "The recording was empty",
                "hint": "Record an answer and try again.",
            },
        )

    settings.ensure_dirs()
    wav_path = settings.AUDIO_TMP_DIR / f"stt_{uuid.uuid4().hex}.wav"
    wav_path.write_bytes(data)

    # `stt.transcribe` deletes the file itself, but the endpoint created it, so
    # it guarantees cleanup too — defense in depth for the privacy promise, and
    # so the file never lingers if transcribe is swapped or stubbed.
    try:
        transcript = await asyncio.to_thread(stt.transcribe, wav_path)
    except stt.VoiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc
    except stt.SttError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc
    finally:
        wav_path.unlink(missing_ok=True)

    return TranscribeResponse(transcript=transcript)


@router.post("/speak", summary="Synthesise speech for a question (WAV audio)")
async def speak(request: SpeakRequest) -> Response:
    """Return spoken WAV audio for `request.text` (used to read questions aloud)."""
    try:
        audio = await asyncio.to_thread(tts.synthesize, request.text)
    except tts.VoiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc
    except tts.TtsError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": exc.message, "hint": exc.hint},
        ) from exc

    return Response(content=audio, media_type="audio/wav")
