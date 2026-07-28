# Offline Test Checklist

**Goal:** prove that AI Career Co-Pilot works with **no internet connection** —
the SOW's headline privacy claim (§6.4, O6: "no resume, interview, voice, or
outreach data leaves the machine; the only network activity is the one-time
model download").

Run this once *before* going offline (the one-time downloads), then disable Wi-Fi
and run everything else. Every step below must pass with networking **off**.

---

## 0. One-time setup (internet ON)

These are the *only* steps that need a network — they download the models to disk.

- [ ] `ollama serve` is running.
- [ ] Open the app → **Setup** tab. It shows Ollama reachable.
- [ ] For each required model still marked "missing", click **Download** and watch
      the progress bar reach 100%:
  - [ ] `llama3.2:3b`  (chat / review / roadmap / outreach / scoring)
  - [ ] `llama3.2:1b`  (fast question-bank generation)
  - [ ] `nomic-embed-text`  (RAG embeddings)
- [ ] (Optional) Voice: if you want voice mode, confirm whisper.cpp + Piper show
      as **installed**. If not, the Setup tab shows "optional, not configured" and
      the rest of the app is unaffected.
- [ ] Setup tab shows **"You're ready — all models installed."**

## 1. Go offline

- [ ] **Disable Wi-Fi / unplug Ethernet.** (Leave `ollama serve` running.)
- [ ] Confirm no connection: `ping 8.8.8.8` fails / browser can't load any site.
- [ ] Launch the app with **`run.bat`** (or the two servers manually).
- [ ] The **Home** dashboard loads. The status dot stays green (local-only).

## 2. Resume + Job Description (RAG ingestion)

- [ ] **Resume** tab → paste/upload a resume → **Save**. It appears in the list.
- [ ] **Job Description** tab → paste a JD → **Save**.
- [ ] No error toasts appear (embedding runs locally via `nomic-embed-text`).

## 3. Resume Review (streamed, 4 stages)

- [ ] **Review** tab → pick the resume + JD → **Run review**.
- [ ] The stepper advances: retrieve → critique → rewrites → keyword gap → ATS.
- [ ] A full report renders (section critique, bullet rewrites, keyword gaps, ATS).
- [ ] Re-open it from **Past reviews** — it loads from the local DB.

## 4. Interview Prep

- [ ] **Interview** tab → pick resume + JD → **Generate questions** (uses 1B; the
      elapsed counter ticks, no "stuck" spinner).
- [ ] Start a mock interview, answer 2–3 questions, **Finish**.
- [ ] The summary shows rubric averages + a score.

## 5. Voice mode (only if configured in step 0)

- [ ] In a mock interview, switch to **Voice**.
- [ ] Play the question (Piper TTS), record an answer, transcribe (whisper.cpp).
- [ ] After transcription, `data/audio_tmp/` is **empty** (audio deleted; only the
      transcript persists — privacy check).

## 6. Career Roadmap

- [ ] **Roadmap** tab → pick a resume, type a target role → **Generate roadmap**.
- [ ] Skill-gap table + three horizon columns render.
- [ ] Tick an action → reload the tab → the tick persisted.

## 7. Outreach Drafter

- [ ] **Outreach** tab → add a contact → fill purpose/platform + a hook →
      **Generate 3 variants**.
- [ ] Three variants render; a LinkedIn note stays ≤ 300 chars (counter).
- [ ] Copy one, mark it **sent** → **replied**; status chips update.

## 8. Dashboard + Settings

- [ ] **Home** dashboard reflects the above (resume count, interview score trend
      sparkline, roadmap %, outreach reply rate).
- [ ] **Settings** → the model dropdown lists your installed models; switching is
      instant (no download).
- [ ] **Settings** → "Where my data lives" shows the local SQLite path.

## 9. Error handling (pull the plug on Ollama)

- [ ] Stop Ollama (`Ctrl+C` in its window). Trigger any AI action.
- [ ] A friendly **toast** appears with the fix ("Ollama is not running… run:
      `ollama serve`") — no stack trace, no infinite spinner.
- [ ] Restart `ollama serve`; the action works again.

## 10. Privacy proof

- [ ] Throughout, **no network requests leave the machine** (optional: watch the
      Windows Resource Monitor "Network" tab — only `ollama.exe` ↔ 127.0.0.1).
- [ ] The single file `data/career_copilot.db` contains all your data (open it with
      any SQLite viewer) — and nothing exists outside it.
- [ ] (Optional) **Settings → Delete ALL my data** (type `DELETE`) wipes it clean.

---

**Pass criteria:** every checkbox above is ticked with Wi-Fi disabled. That
demonstrates a fully local, zero-cost, private career assistant — the answer to
the viva question *"why not just use ChatGPT?"*
