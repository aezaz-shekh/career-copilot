"""Tests for the voice pipeline (Phase 2a).

whisper.cpp and Piper are external binaries, so subprocess.run is mocked. The
tests pin the two things that matter most: the command construction and the
privacy guarantee (audio is always deleted).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import stt, tts

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_audio_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Keep every test's temp audio out of the real data/audio_tmp directory."""
    audio = tmp_path / "audio_tmp"
    audio.mkdir()
    monkeypatch.setattr(get_settings(), "AUDIO_TMP_DIR", audio)
    return audio


@pytest.fixture
def voice_paths(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point config at fake-but-present binary/model files."""
    settings = get_settings()
    whisper_bin = tmp_path / "whisper-cli.exe"
    whisper_model = tmp_path / "ggml-tiny.en.bin"
    piper_bin = tmp_path / "piper.exe"
    piper_voice = tmp_path / "voice.onnx"
    for f in (whisper_bin, whisper_model, piper_bin, piper_voice):
        f.write_bytes(b"stub")

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    monkeypatch.setattr(settings, "WHISPER_BIN", whisper_bin)
    monkeypatch.setattr(settings, "WHISPER_MODEL", whisper_model)
    monkeypatch.setattr(settings, "PIPER_BIN", piper_bin)
    monkeypatch.setattr(settings, "PIPER_VOICE", piper_voice)
    monkeypatch.setattr(settings, "AUDIO_TMP_DIR", audio_dir)
    return settings


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


def test_unavailable_when_binaries_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "WHISPER_BIN", Path("nope/whisper-cli.exe"))
    monkeypatch.setattr(settings, "WHISPER_MODEL", Path("nope/model.bin"))
    monkeypatch.setattr(settings, "PIPER_BIN", Path("nope/piper.exe"))
    monkeypatch.setattr(settings, "PIPER_VOICE", Path("nope/voice.onnx"))
    # Also block PATH resolution.
    monkeypatch.setattr(stt.shutil, "which", lambda name: None)
    monkeypatch.setattr(tts.shutil, "which", lambda name: None)

    assert stt.stt_available() is False
    assert tts.tts_available() is False


def test_available_when_files_present(voice_paths) -> None:
    assert stt.stt_available() is True
    assert tts.tts_available() is True


def test_status_endpoint_reports_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stt, "stt_available", lambda: False)
    monkeypatch.setattr(tts, "tts_available", lambda: False)

    body = client.get("/api/voice/status").json()

    assert body == {"stt_available": False, "tts_available": False}


# --------------------------------------------------------------------------- #
# STT
# --------------------------------------------------------------------------- #


def test_transcribe_builds_command_and_deletes_audio(
    voice_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav = voice_paths.AUDIO_TMP_DIR / "a.wav"
    wav.write_bytes(b"RIFF....WAVE")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="Hello there.\n", stderr="")

    monkeypatch.setattr(stt.subprocess, "run", fake_run)

    text = stt.transcribe(wav)

    assert text == "Hello there."
    assert "-nt" in captured["cmd"] and "-f" in captured["cmd"]
    assert str(voice_paths.WHISPER_MODEL) in captured["cmd"]
    # Privacy: the audio file is gone.
    assert not wav.exists()


def test_transcribe_deletes_audio_even_on_failure(
    voice_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav = voice_paths.AUDIO_TMP_DIR / "b.wav"
    wav.write_bytes(b"RIFF")

    def boom(cmd, **kwargs):
        raise OSError("binary crashed")

    monkeypatch.setattr(stt.subprocess, "run", boom)

    with pytest.raises(stt.SttError):
        stt.transcribe(wav)
    assert not wav.exists()  # deleted despite the crash


def test_transcribe_timeout_is_friendly(voice_paths, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = voice_paths.AUDIO_TMP_DIR / "c.wav"
    wav.write_bytes(b"RIFF")

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(stt.subprocess, "run", slow)

    with pytest.raises(stt.SttError, match="timed out"):
        stt.transcribe(wav)
    assert not wav.exists()


def test_transcribe_missing_binary_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "WHISPER_BIN", Path("nope.exe"))
    monkeypatch.setattr(settings, "WHISPER_MODEL", Path("nope.bin"))
    monkeypatch.setattr(stt.shutil, "which", lambda name: None)

    wav = tmp_path / "d.wav"
    wav.write_bytes(b"RIFF")

    with pytest.raises(stt.VoiceUnavailableError):
        stt.transcribe(wav)
    assert not wav.exists()  # still cleaned up


# --------------------------------------------------------------------------- #
# TTS
# --------------------------------------------------------------------------- #


def test_synthesize_returns_audio_and_deletes_temp(
    voice_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = {}

    def fake_run(cmd, **kwargs):
        out_path = Path(cmd[cmd.index("-f") + 1])
        out_path.write_bytes(b"RIFF-fake-wav")
        created["path"] = out_path
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(tts.subprocess, "run", fake_run)

    audio = tts.synthesize("Tell me about yourself.")

    assert audio == b"RIFF-fake-wav"
    assert not created["path"].exists()  # temp cleaned up


def test_synthesize_missing_binary_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "PIPER_BIN", Path("nope.exe"))
    monkeypatch.setattr(settings, "PIPER_VOICE", Path("nope.onnx"))
    monkeypatch.setattr(tts.shutil, "which", lambda name: None)

    with pytest.raises(tts.VoiceUnavailableError):
        tts.synthesize("hello")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def test_transcribe_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stt, "transcribe", lambda path: "I fixed a production bug.")

    response = client.post(
        "/api/voice/transcribe",
        files={"file": ("answer.wav", b"RIFF....WAVE", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["transcript"] == "I fixed a production bug."


def test_transcribe_endpoint_cleans_up_even_if_service_does_not(
    isolate_audio_dir, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stubbed transcribe that skips deletion must not leave a file behind:
    the endpoint's own finally guarantees the audio is removed."""
    monkeypatch.setattr(stt, "transcribe", lambda path: "kept nothing")

    client.post("/api/voice/transcribe", files={"file": ("a.wav", b"RIFF....WAVE", "audio/wav")})

    assert list(isolate_audio_dir.iterdir()) == []  # no leaked audio


def test_transcribe_endpoint_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    response = client.post("/api/voice/transcribe", files={"file": ("a.wav", b"", "audio/wav")})
    assert response.status_code == 422


def test_transcribe_endpoint_501_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(path):
        raise stt.VoiceUnavailableError("no whisper", hint="install it")

    monkeypatch.setattr(stt, "transcribe", unavailable)

    response = client.post("/api/voice/transcribe", files={"file": ("a.wav", b"RIFF", "audio/wav")})
    assert response.status_code == 501
    assert "hint" in response.json()["detail"]


def test_speak_endpoint_returns_wav(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts, "synthesize", lambda text: b"RIFF-audio")

    response = client.post("/api/voice/speak", json={"text": "Question one."})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-audio"


def test_speak_endpoint_501_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(text):
        raise tts.VoiceUnavailableError("no piper", hint="install it")

    monkeypatch.setattr(tts, "synthesize", unavailable)

    response = client.post("/api/voice/speak", json={"text": "hi"})
    assert response.status_code == 501


# --------------------------------------------------------------------------- #
# VOICE_ENABLED kill switch
#
# Small hosts cannot hold whisper and Piper alongside the app, so voice has to
# be switchable off from the environment even when the binaries are installed.
# --------------------------------------------------------------------------- #


def test_voice_reports_unavailable_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_ENABLED", "false")
    get_settings.cache_clear()

    assert stt.stt_available() is False
    assert tts.tts_available() is False

    body = TestClient(app).get("/api/voice/status").json()
    assert body["stt_available"] is False
    assert body["tts_available"] is False

    get_settings.cache_clear()
