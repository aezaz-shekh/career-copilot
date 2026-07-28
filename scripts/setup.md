# Setup Guide — AI Career Co-Pilot (Windows)

Every tool below is free. There is no account to create, no credit card, and no
API key anywhere in this project. After the one-time model download in Step 2,
the whole application runs with your network disabled.

**Reference machine for this guide:** Windows 11, 8 GB RAM, no GPU.

---

## Step 0 — What you need installed

| Tool | Version | Check with |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js | 18+ (22 recommended) | `node --version` |
| Git | any recent | `git --version` |
| Ollama | latest | `ollama --version` |

### Fast path — winget (verified working on the reference machine)

If you have `winget` (built into Windows 11), these two commands replace the
manual downloads in Step 0 and Step 1:

```powershell
winget install --id Python.Python.3.12 -e --scope user
winget install --id Ollama.Ollama -e
```

Then **close and reopen your terminal** — PATH changes only apply to new
sessions — and skip to Step 2. The manual instructions below are the fallback.

### Install Python 3.12

Download the **Windows installer (64-bit)** from
<https://www.python.org/downloads/release/python-3129/>

On the first screen of the installer, **tick "Add python.exe to PATH"** before
clicking Install. If you skip this, every command below fails with
*"Python was not found"*.

Then close and reopen your terminal and verify:

```powershell
python --version
```

Expected: `Python 3.12.9` (any 3.12.x is fine).

> If Windows opens the Microsoft Store instead of printing a version, the
> Store alias is shadowing your install. Turn it off under
> **Settings → Apps → Advanced app settings → App execution aliases** — switch
> off `python.exe` and `python3.exe`.

### Install Node.js

Download the LTS installer from <https://nodejs.org/> and accept the defaults.

```powershell
node --version
npm --version
```

---

## Step 1 — Install Ollama (the local LLM runtime)

Download **OllamaSetup.exe** from <https://ollama.com/download/windows> and run it.
Ollama installs as a background service and listens on `127.0.0.1:11434`.

Verify:

```powershell
ollama --version
curl http://127.0.0.1:11434/api/tags
```

The `curl` call should return JSON (an empty model list is expected at this point).
If it errors, start the service manually in its own terminal window:

```powershell
ollama serve
```

---

## Step 2 — Download the two models (one time, ~2.3 GB total)

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

| Model | Size | Role |
|---|---|---|
| `llama3.2:3b` | ~2.0 GB | All text generation, critique and scoring |
| `nomic-embed-text` | ~274 MB | Embeddings for RAG retrieval |

Confirm both arrived:

```powershell
ollama list
```

> **Why 3B and not 8B?** The SOW names `llama3.1:8b` for a ≥16 GB reference
> machine and documents an 8 GB fallback tier (§11, risk register). On 8 GB with
> no GPU, an 8B model swaps to disk and each response takes minutes.
> `llama3.2:3b` is that fallback tier — newer and stronger than the `phi3.5` /
> `gemma2:2b` the SOW originally proposed. To try another model later, change
> `CHAT_MODEL` in `backend/.env` — no code changes needed.

Smoke-test the model directly (first run is slow; it loads ~2 GB into RAM):

```powershell
ollama run llama3.2:3b "Say hello in one short sentence."
```

Type `/bye` to exit.

---

## Step 3 — Backend setup

From the repository root (`career-copilot/`):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Your prompt should now start with `(.venv)`. If PowerShell blocks the activate
script with *"running scripts is disabled on this system"*, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Start the API (from inside `backend/`, with the venv active):

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Leave this terminal running. Check it:

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>

---

## Step 4 — Frontend setup

In a **second** terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. You should see the **"Local AI: Connected"** badge
in green.

The Vite dev server proxies `/health` and `/api/*` to the backend on port 8000,
so the browser only ever talks to one origin.

> Creating this frontend from scratch would be
> `npm create vite@latest frontend -- --template react`, then adding
> `tailwindcss` and `@tailwindcss/vite`. Those files are already committed here,
> so `npm install` is all you need.

---

## Step 5 — Seed sample data (optional)

Inserts one sample resume and one sample job description so the resume and
interview modules have something to work with. Run from the repository root:

```powershell
backend\.venv\Scripts\python.exe scripts\seed.py
```

Re-running is safe — it detects existing sample rows. Use `--reset` to replace
them.

The pair is chosen so keyword-gap analysis has real overlaps (Python, SQL, REST,
Git) and real gaps (FastAPI, Docker, CI/CD, pytest, PostgreSQL) to find.

---

## Step 6 — Run the tests

From `backend/` with the venv active:

```powershell
pytest
ruff check .
ruff format --check .
```

All tests stub the LLM client, so they pass **without** Ollama running and
finish in about a second.

---

## Daily startup (after setup is done)

| Terminal | Directory | Command |
|---|---|---|
| 1 | `backend` | `.venv\Scripts\activate` then `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| 2 | `frontend` | `npm run dev` |

Ollama runs on its own in the background; you only need `ollama serve` if the
health badge reports it as offline.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Badge red, "Backend not running" | Uvicorn isn't up | Start terminal 1 (see above) |
| Badge red, "Ollama is not running" | Service stopped | Run `ollama serve` |
| Badge amber, "model not downloaded" | Missing pull | Run the `ollama pull` shown on screen |
| `ModuleNotFoundError: app` | Wrong directory | `uvicorn` must run from `backend/`, not the repo root |
| `python: command not found` | PATH not set | Reinstall Python with "Add to PATH" ticked |
| First reply takes 30–60 s | Model loading into RAM | Normal on 8 GB; later replies are much faster |
| Whole machine crawls during generation | RAM pressure | Close Chrome tabs / other apps; 3B needs ~3 GB free |

---

## Proving the privacy claim (needed for the viva — SOW §9)

Once both models are pulled:

1. Disconnect Wi-Fi / unplug the network cable.
2. Restart both servers and use the app normally.
3. Everything still works — the only network call this project ever makes is the
   one-time model download in Step 2.
