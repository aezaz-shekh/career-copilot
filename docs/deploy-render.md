# Deploying to Render (free tier, no credit card)

Result: a permanent public URL — `https://career-copilot.onrender.com` — that
your examiner can open at any time with your laptop switched off, answering in
seconds rather than minutes.

## What runs where

| Concern | On your laptop | On Render |
|---|---|---|
| UI | Vite dev server, port 5173 | Built once, served by FastAPI |
| API | uvicorn, port 8000 | Same app, on `$PORT` |
| Chat generation | Ollama, local CPU (1–3 min) | Groq via `hf/ollama_shim.py` (seconds) |
| Embeddings | `nomic-embed-text` in Ollama | `fastembed` (bge-small) in the container |
| Voice | whisper.cpp + Piper (Windows) | whisper.cpp + Piper (Linux, built in image) |

No file under `backend/app/` changes. The shim reimplements the three Ollama
endpoints the app calls, so `OllamaClient` cannot tell the difference.

---

## Step 1 — Accounts (both free, no card)

1. **GitHub** — https://github.com/signup (Render deploys from a repo)
2. **Render** — https://render.com → *Get Started* → sign in **with GitHub**
3. **Groq** — https://console.groq.com → *API Keys* → **Create API Key** → copy it

## Step 2 — Push the project to GitHub

Create an empty repo at https://github.com/new named `career-copilot`
(**private is fine**), then from PowerShell:

```powershell
cd "d:\AI Career Co-Pilot Project\career-copilot"
git init
git add .
git commit -m "AI Career Co-Pilot"
git branch -M main
git remote add origin https://github.com/<GH-USERNAME>/career-copilot.git
git push -u origin main
```

`.gitignore` already excludes `node_modules/`, `.venv/`, `data/` and `voice/`,
so the push stays small and no personal data leaves your machine.

## Step 3 — Create the Render service

The repository has a `render.yaml`, so the quickest path is
https://dashboard.render.com → **New** → **Blueprint** → connect the repo:
Render reads the file and fills in the runtime, Dockerfile path, build context,
plan, health check and `VOICE_ENABLED` itself. You only supply the two secrets
in Step 4.

To configure it by hand instead (**New** → **Web Service**):

| Field | Value |
|---|---|
| Language / Runtime | **Docker** |
| Dockerfile Path | `./hf/Dockerfile` |
| Docker Build Context Directory | `.` |
| Instance Type | **Free** |
| Health Check Path | `/health` |

The build context must be the repository root — the Dockerfile copies
`backend/`, `frontend/` and `prompts/`.

## Step 4 — Environment variables

In the same form (or Settings → Environment) add:

| Key | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `APP_PASSWORD` | a password you choose |

(`VOICE_ENABLED=false` and `INFERENCE_PROVIDER=Groq` come from `render.yaml`.)

Login will be `examiner` / that password. Without `APP_PASSWORD` the app is
wide open — it has no login of its own, so anyone with the URL could read
uploaded resumes.

Do **not** set `PORT`; Render injects it and `start.sh` reads it.

## Step 5 — Deploy and wait

First build takes roughly **10–20 minutes** — whisper.cpp compiles from source,
Piper and its voice download, `npm ci && npm run build` runs, and the embedding
model is baked in. Later builds are cached and much faster.

When the log shows `Uvicorn running`, open your URL.

---

## Verifying

| Check | Expected |
|---|---|
| Page loads | UI renders after the browser login prompt |
| Badge | **Connected**, not Offline |
| Ask a question | Answer in seconds |
| Status tab | No missing models |
| Mock interview | Runs in text mode (voice is off on the free tier) |

---

## The free tier's real limits

**512 MB RAM — the main risk.** The app, `fastembed`, whisper and Piper share
it. Idle sits around 300–400 MB; transcription can push past the cap and get
the process OOM-killed (Render shows "Out of memory" and restarts).

Voice is therefore **off by default here**: `render.yaml` sets
`VOICE_ENABLED=false`, and `stt_available()` / `tts_available()` return `False`
so the app stays in text mode by design — no code change, no crash. The other
four modules are unaffected.

(Deleting `WHISPER_BIN` / `PIPER_BIN` in the dashboard also works, but those are
`ENV` lines in the Dockerfile and the dashboard cannot unset them, only blank
them — `VOICE_ENABLED` is the explicit switch.)

To try voice anyway, set `VOICE_ENABLED=true` on a paid instance with more
memory. On the free tier expect the process to be OOM-killed mid-transcription.

**Spins down after 15 minutes idle.** The next visitor waits ~50 seconds while
it restarts. Prevent it with a free **UptimeRobot** monitor hitting
`https://<your-app>.onrender.com/health` every 5 minutes — `/health` is
deliberately exempt from the password in `hf/server.py`.

**Storage is ephemeral.** `career_copilot.db` resets on every restart or
redeploy, so uploads and history do not persist between sessions.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails at `npm ci` | `package-lock.json` not committed | Commit it |
| Build fails downloading Piper | Release asset renamed | Check https://github.com/rhasspy/piper/releases and update the version in the Dockerfile |
| Deploy succeeds, 502 on open | App still booting | Wait; check logs for `Uvicorn running` |
| "Out of memory" in logs | 512 MB exceeded | Remove `WHISPER_BIN` / `PIPER_BIN` (see above) |
| Answers fail 401/403 | Bad `GROQ_API_KEY` | Re-add it, redeploy |
| Answers fail 429 | Groq free-tier rate limit | Wait a minute and retry |
| App shows **Offline** | Shim not running | Check logs for `ollama_shim` errors |

## Note for the report

The project is local-first: on a laptop it runs entirely offline against Ollama,
with no API keys and no data leaving the machine. This deployment is an
**optional hosted mode** that swaps the inference runtime behind an unchanged
internal API. That the swap required no application changes is evidence the LLM
transport was properly isolated in `app/llm/client.py`.
