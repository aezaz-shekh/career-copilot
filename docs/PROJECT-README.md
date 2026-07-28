# AI Career Co-Pilot

**A privacy-first, local-first, zero-cost AI career assistant.**
Run it on your machine and there are no cloud services, no API keys and no
subscriptions: every byte of your data stays on your own disk, and the only
network request the app makes is a one-time model download. An optional
[hosted mode](#hosted-mode) exists so the project can be tried without
installing anything.

> BCA Final-Year Major Project · built to the Statement of Work v2.0.
> All five modules are complete and tested.

> **Live demo:** <https://aezazshekh-career-copilot.hf.space> (login `examiner`).
> The hosted build swaps the inference runtime behind an unchanged internal API
> — see [Hosted mode](#hosted-mode) below.

---

## Why this exists

Job seekers — especially fresh graduates — need to tailor resumes, rehearse
interviews, plan skills, and write outreach. Existing AI tools do this but
require uploading your entire career history to a third-party cloud and usually
charge a subscription. **AI Career Co-Pilot does all of it locally**, using an
open-weight LLM served through [Ollama](https://ollama.com). It's the
demonstrable answer to *"why not just use ChatGPT?"* — because your resume,
spoken interview answers, and contacts never leave your disk.

---

## Features (the five modules)

| # | Module | What it does |
|---|--------|--------------|
| 1 | **Resume Review & Tailoring** | Section-by-section critique, bullet rewrites, keyword-gap report vs. a job description, and an ATS-readability checklist — streamed live. |
| 2 | **Interview Prep & Mock Interviews** | Generates a grounded behavioural + technical question bank, then runs a scored mock interview with rubric feedback. |
| 3 | **Voice Mock Interviews** | The same interview, spoken — local speech-to-text (whisper.cpp) and text-to-speech (Piper). Fully optional. |
| 4 | **Career Path & Skill-Gap Guidance** | A skill-gap table (judged from your resume) and a phased *now / 3-month / 12-month* roadmap you can tick off. |
| 5 | **Networking / Outreach Drafter** | Three toned, length-capped message variants (LinkedIn note / InMail / email) grounded in your resume and target role. |

Plus a **cross-feature dashboard**, a **first-run setup wizard** with model
auto-download, a **settings** page (switch models, delete all data), and
friendly error handling throughout.

### Screenshots

> Drop PNGs into `docs/screenshots/` using the filenames below and this table
> renders itself. Until then the links are intentionally absent rather than
> broken.

`dashboard.png` · `review.png` · `interview.png` · `roadmap.png` ·
`outreach.png` · `setup.png`

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 · Vite 6 · Tailwind CSS v4 |
| Backend | Python 3.12 · FastAPI · Uvicorn · SQLAlchemy 2.0 · Pydantic v2 |
| Data | SQLite + [`sqlite-vec`](https://github.com/asg017/sqlite-vec) (vector search in one file) |
| LLM runtime | Ollama — `llama3.2:3b` (reasoning), `llama3.2:1b` (fast question gen), `nomic-embed-text` (embeddings) |
| Voice (optional) | whisper.cpp (STT) · Piper (TTS) |
| Quality | pytest (209 tests, stubbed LLM) · Ruff · a real-model evaluation harness |

Everything is free and open-source. **₹0 ongoing cost.**

---

## Quick start

### Prerequisites
- **Python 3.12+**, **Node.js 18+**, and **[Ollama](https://ollama.com/download)** installed.
- ~8 GB RAM (the app is tuned for an 8 GB, no-GPU machine).

### One-time model download (needs internet, once)
```powershell
ollama pull llama3.2:3b
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```
Or skip this and use the app's **Setup** tab, which downloads them with a
progress bar.

### Fastest way to run — one command (Windows)
From the `career-copilot/` folder, double-click **`run.bat`** (or run it in a
terminal). It starts the backend and frontend in their own windows and opens the
browser.

### Manual run (any OS)
```powershell
# One-time backend setup
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```
Then open **<http://127.0.0.1:5173>**. Make sure `ollama serve` is running.

> First run? Open the **Setup** tab — it checks Ollama, offers to download any
> missing models, and reports whether optional voice is configured.

---

## Project layout

```
career-copilot/
├── run.bat                 # one-command launcher (Windows)
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI entry point + global error handlers
│   │   ├── config.py       # every setting: model names, paths, temperatures, timeouts
│   │   ├── runtime_config.py  # user-switchable active model (persists across restarts)
│   │   ├── routers/        # one file per module (resume, review, interviews, roadmap, outreach, voice, setup, settings, stats)
│   │   ├── services/       # business + AI orchestration
│   │   ├── llm/            # Ollama client, prompt loader, RAG pipeline
│   │   ├── models/         # SQLAlchemy ORM (the entities in the ER diagram)
│   │   └── schemas/        # Pydantic contracts (also the JSON schemas sent to Ollama)
│   └── tests/
│       ├── test_*.py       # 209 pytest tests, LLM stubbed
│       ├── eval_harness.py # real-model benchmark (run by hand)
│       └── fixtures/       # 5 resume/JD pairs + outreach scenarios
├── frontend/               # React 18 + Vite + Tailwind (one page per module)
├── prompts/                # versioned .txt prompt templates (string.Template syntax)
├── docs/                   # this documentation set
├── scripts/                # setup guide, DB seed helper
└── data/                   # SQLite DB + temp audio (git-ignored, never leaves your disk)
```

---

## Privacy guarantee

- Both servers bind to **`127.0.0.1` only** — unreachable from the network.
- All inference runs locally through Ollama.
- The **only** outbound request the project ever makes is the one-time model pull.
- No telemetry, no analytics, no crash reporting.
- Voice audio is transcribed then **deleted immediately**; only the transcript text persists.
- `data/` holds everything in one SQLite file. Delete it (or use **Settings →
  Delete ALL my data**) and nothing remains.

Prove it yourself: follow **[docs/offline-test-checklist.md](docs/offline-test-checklist.md)**
with Wi-Fi disabled.

### Hosted mode

Everything above describes the default: run it on your machine and no text ever
leaves it. The public demo is a second, optional mode. Free CPU hosting cannot
run a 3B model at interactive speed, so there chat is answered by a hosted
provider (Groq) through an Ollama-compatible shim; embeddings, speech and the
database still run inside the container.

No file under `backend/app/` differs between the two modes — the swap happens
behind `OLLAMA_URL`, which is the point: the LLM transport is isolated in
`app/llm/client.py`. The app reports which mode it is in on `/health`, and the
interface labels itself accordingly rather than claiming "local" in both.

---

## Testing

```powershell
cd backend
.venv\Scripts\python.exe -m pytest       # 209 unit/integration tests (stubbed LLM, fast)
.venv\Scripts\python.exe -m ruff check .  # lint

# Real-model benchmark (needs Ollama; writes eval_results.md)
.venv\Scripts\python.exe tests\eval_harness.py
```

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/user-manual.md](docs/user-manual.md) | How to use each module, with tips |
| [docs/architecture.md](docs/architecture.md) | System architecture, DFDs, use-case diagram |
| [docs/er-diagram.md](docs/er-diagram.md) | Entity-relationship diagram + design rationale |
| [docs/test-cases.md](docs/test-cases.md) | 25-case manual test table |
| [docs/viva-demo-script.md](docs/viva-demo-script.md) | 10-minute demo script + viva Q&A |
| [docs/offline-test-checklist.md](docs/offline-test-checklist.md) | Wi-Fi-off privacy verification |
| [docs/voice-setup.md](docs/voice-setup.md) | Installing whisper.cpp + Piper |

---

## FAQ

**Do I need a GPU?** No. It runs on CPU. The models are chosen for an 8 GB
machine; generation takes seconds to a couple of minutes depending on the task.

**Does it work offline?** Yes — after the one-time model download, disable Wi-Fi
and everything still works. That's the whole point.

**Why two chat models?** `llama3.2:3b` handles reasoning-heavy work (review,
scoring, roadmap, outreach). Question-bank generation uses the faster
`llama3.2:1b` because those questions are templated and grounded enough that the
smaller model is plenty — and it keeps generation near ~30 s.

**Generation feels slow / "stuck".** On an 8 GB machine the model competes for
RAM. Close spare browser tabs and heavy apps; the long operations stream live
progress so you can see they're working, not frozen.

**Is my data used to train anything?** No. There is no cloud, no account, and no
telemetry. The model is a local file.

**Can I switch models?** Yes — **Settings → Active chat model** lists everything
you've pulled and switches instantly, no restart.

**Is the voice feature required?** No. It's optional; if whisper.cpp/Piper aren't
installed the app runs fully in text mode and says so.
