# Voice Mode Setup — whisper.cpp + Piper (Windows, CPU-only)

Voice mode is **optional**. The whole app works without it — the interview runs
in text mode, and the app never errors just because these binaries are missing.
Install this only if you want spoken mock interviews.

Everything here is free and local. No account, no API key, no cloud.

**Reference machine:** Windows 11, 8 GB RAM, no GPU. We use the **smallest**
model tiers (whisper `tiny.en`, a medium Piper voice) so voice does not starve
the LLM of RAM (SOW §11).

All files go under `career-copilot/voice/` (git-ignored). Create it first:

```powershell
cd "d:\Career Co-Pilot Project\career-copilot"
New-Item -ItemType Directory -Force voice\whisper, voice\piper | Out-Null
```

---

## 1. whisper.cpp (speech-to-text)

### 1a. Download the prebuilt Windows binary

whisper.cpp ships prebuilt CPU binaries — no compiling needed.

1. Open <https://github.com/ggml-org/whisper.cpp/releases>
2. Download the latest **`whisper-bin-x64.zip`** (Windows, x64, CPU/BLAS).
3. Extract it and copy the contents (including `whisper-cli.exe` and its DLLs)
   into `career-copilot\voice\whisper\`.

```powershell
# After extracting the zip to, say, %USERPROFILE%\Downloads\whisper-bin-x64\
Copy-Item "$env:USERPROFILE\Downloads\whisper-bin-x64\*" `
          "d:\Career Co-Pilot Project\career-copilot\voice\whisper\" -Recurse -Force
```

Confirm the binary runs:

```powershell
cd "d:\Career Co-Pilot Project\career-copilot\voice\whisper"
.\whisper-cli.exe --help
```

> Older releases name the binary `main.exe` instead of `whisper-cli.exe`. If so,
> either rename it to `whisper-cli.exe`, or set `WHISPER_BIN` in `backend\.env`
> to the real name.

### 1b. Download the tiny.en model (~75 MB)

```powershell
cd "d:\Career Co-Pilot Project\career-copilot\voice\whisper"
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin" `
  -OutFile "ggml-tiny.en.bin"
```

You should now have:

```
voice\whisper\whisper-cli.exe
voice\whisper\ggml-tiny.en.bin
```

---

## 2. Piper (text-to-speech)

### 2a. Download the Piper binary

1. Open <https://github.com/rhasspy/piper/releases>
2. Download **`piper_windows_amd64.zip`**.
3. Extract it into `career-copilot\voice\piper\` (keep `piper.exe` and its DLLs
   together).

```powershell
Copy-Item "$env:USERPROFILE\Downloads\piper_windows_amd64\piper\*" `
          "d:\Career Co-Pilot Project\career-copilot\voice\piper\" -Recurse -Force
```

### 2b. Download one English voice (~60 MB)

Each voice is two files: the `.onnx` model and its `.onnx.json` config. Both
must sit next to each other.

```powershell
cd "d:\Career Co-Pilot Project\career-copilot\voice\piper"
$base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
Invoke-WebRequest -Uri "$base/en_US-lessac-medium.onnx"      -OutFile "en_US-lessac-medium.onnx"
Invoke-WebRequest -Uri "$base/en_US-lessac-medium.onnx.json" -OutFile "en_US-lessac-medium.onnx.json"
```

Test it:

```powershell
"Hello, this is a local voice." | .\piper.exe -m en_US-lessac-medium.onnx -f test.wav
Start-Process test.wav   # should play speech
Remove-Item test.wav
```

You should now have:

```
voice\piper\piper.exe
voice\piper\en_US-lessac-medium.onnx
voice\piper\en_US-lessac-medium.onnx.json
```

---

## 3. Verify the app sees them

Restart the backend, then check the capability endpoint:

```powershell
curl http://127.0.0.1:8000/api/voice/status
```

Expected once both are installed:

```json
{ "stt_available": true, "tts_available": true }
```

Reload the app — the interview screen now shows a **Text / Voice** toggle. In
voice mode the question is read aloud and you answer by microphone.

---

## Default paths (override in `backend\.env` if you put things elsewhere)

| Setting | Default |
|---|---|
| `WHISPER_BIN` | `voice\whisper\whisper-cli.exe` |
| `WHISPER_MODEL` | `voice\whisper\ggml-tiny.en.bin` |
| `PIPER_BIN` | `voice\piper\piper.exe` |
| `PIPER_VOICE` | `voice\piper\en_US-lessac-medium.onnx` |

Any of these can point at a binary already on your PATH — the app resolves a
bare command name via PATH as well as an absolute path.

---

## Privacy (SOW §6.4)

- The browser records audio and uploads it once. The backend writes it to a
  temp file under `data\audio_tmp\`, transcribes it, and **deletes it
  immediately** — even if transcription fails.
- Only the transcript text is ever stored, and you can **edit the transcript
  before submitting**, so an STT mistake never becomes part of your record.
- TTS audio is generated to a temp file, streamed once, and deleted. Nothing
  spoken or heard is kept.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `status` shows `false` after install | Check the four files exist at the paths above; restart the backend |
| "whisper.cpp is not installed" mid-interview | The `.exe` moved or a DLL is missing — re-extract the full zip |
| Piper plays nothing | The `.onnx.json` must sit next to the `.onnx` |
| Mic does nothing in the browser | Allow microphone permission for `127.0.0.1`; the app falls back to text if denied |
| Transcription is slow | Normal on first use (model load). `tiny.en` is the fastest tier |
