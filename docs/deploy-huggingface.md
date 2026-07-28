# Deploying to Hugging Face Spaces (free, no credit card)

Result: a permanent public URL the examiner can open at any time, with your
laptop switched off, answering in seconds rather than minutes.

## How it works

| Concern | On your laptop | On the Space |
|---|---|---|
| UI | Vite dev server, port 5173 | Built once, served by FastAPI |
| API | uvicorn, port 8000 | Same app, port 7860 |
| Chat generation | Ollama, local CPU (1–3 min) | Groq via a shim (seconds) |
| Embeddings | `nomic-embed-text` in Ollama | `fastembed` inside the container |

`hf/ollama_shim.py` reimplements the three Ollama endpoints the app uses
(`/api/tags`, `/api/chat`, `/api/embed`) and forwards chat to Groq. The app
still talks to `OLLAMA_URL`, so **no file under `backend/app/` changes**.

---

## Step 1 — Accounts (both free, no card)

1. **Hugging Face** — https://huggingface.co/join
2. **Groq** — https://console.groq.com → *API Keys* → **Create API Key** → copy it
   (shown once)

## Step 2 — Create the Space

https://huggingface.co/new-space

- **Owner:** your username
- **Space name:** `career-copilot`
- **License:** any
- **SDK:** **Docker** → *Blank*
- **Hardware:** CPU basic (free)
- **Visibility:** Public

## Step 3 — Add secrets

Space → **Settings** → **Variables and secrets** → *New secret*:

| Name | Value | Kind |
|---|---|---|
| `GROQ_API_KEY` | your Groq key | **Secret** |
| `APP_PASSWORD` | a password you choose | **Secret** |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Variable |

`APP_PASSWORD` is optional but recommended: a Space is public, and the app has
no login of its own, so without it anyone who finds the URL can read uploaded
resumes. Username is `examiner` unless you set `APP_USER`.

## Step 4 — Push the code

From the project root (`career-copilot`), in PowerShell:

```powershell
# One-time: install git-lfs if you have not already
git init
git add .
git commit -m "AI Career Co-Pilot"

# Space README must be at the repo root with the YAML header
Copy-Item hf\README-space.md README.md -Force
Copy-Item hf\Dockerfile Dockerfile -Force

git add README.md Dockerfile
git commit -m "Add Space configuration"

git remote add space https://huggingface.co/spaces/<USERNAME>/career-copilot
git push space main
```

You will be asked for your Hugging Face username and an **access token** as the
password — create one at https://huggingface.co/settings/tokens with *write*
scope.

> The `Dockerfile` must sit at the repository root because its build context is
> the root (it copies `backend/`, `frontend/` and `prompts/`).

## Step 5 — Watch the build

The Space shows a build log. First build takes roughly **5–10 minutes**: it
installs Python dependencies, runs `npm ci && npm run build`, and bakes the
embedding model into the image.

When it says **Running**, open:

```
https://huggingface.co/spaces/<USERNAME>/career-copilot
```

Log in with `examiner` / your `APP_PASSWORD`, then ask a question. The first
reply should arrive in a few seconds.

---

## Verifying

| Check | Expected |
|---|---|
| Page loads | UI renders, badge shows **Connected** |
| Status tab | Ollama "reachable", no missing models |
| Ask a question | Answer in seconds, not minutes |
| Resume upload → review | Works (RAG uses local embeddings) |

## Known limits of the free tier

- **Sleeps after ~48 h idle.** The next visitor waits 1–2 minutes while it wakes.
  It does not break; it is just cold.
- **Storage is ephemeral.** `career_copilot.db` resets whenever the Space
  restarts or rebuilds, so uploads and history do not persist.
- **Voice works.** The image compiles whisper.cpp and installs Piper's Linux
  build, then points `WHISPER_BIN`, `WHISPER_MODEL`, `PIPER_BIN` and
  `PIPER_VOICE` at them. No application code changes — those are settings, and
  `stt.py` / `tts.py` invoke the binaries with identical flags on every
  platform. The browser records 16 kHz mono WAV, so no server-side audio
  conversion is needed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails at `npm ci` | `package-lock.json` not committed | Commit it |
| Build fails downloading Piper | Release asset URL changed | Check https://github.com/rhasspy/piper/releases and update the version in the Dockerfile |
| Voice buttons greyed out | `/voice/status` reports false | Check the build log for whisper/Piper errors |
| Space runs, app shows **Offline** | Shim not up | Check logs for `ollama_shim` errors |
| Answers fail with 401/403 | Bad or missing `GROQ_API_KEY` | Re-add the secret, restart the Space |
| Answers fail with 429 | Groq free-tier rate limit | Wait, or lower request volume |
| Blank page, API works | `dist/` missing | Confirm stage 1 of the Dockerfile succeeded |

## Note for the report

State the architecture honestly: the project is local-first (Ollama, no API
keys, nothing leaves the device), and this deployment is an **optional hosted
mode** that swaps the inference runtime behind an unchanged internal API. That
the swap needed no application changes is a point in favour of the design — it
shows the LLM transport was properly isolated in `app/llm/client.py`.
