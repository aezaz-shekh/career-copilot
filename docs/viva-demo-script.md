# 10-Minute Viva Demo Script + Q&A — AI Career Co-Pilot

A tight, rehearsed run that shows all five modules and the privacy story, then a
bank of likely viva questions with strong answers.

---

## Before the examiner arrives (setup — do NOT do this live)

1. Start `ollama serve`.
2. Launch the app with **`run.bat`**; confirm the **Setup** tab is all green.
3. **Pre-load one resume and one JD** so you don't waste demo time pasting:
   - Resume: *Aarav Sharma — Junior Developer* (from
     `backend/tests/fixtures/pairs/01_junior_developer.json`).
   - JD: *Junior Python Developer — TechNova* (same file).
4. Optionally pre-generate one interview and one roadmap so a saved example is
   ready if generation is slow on the day.
5. Close spare browser tabs and heavy apps to free RAM.

> **Timing tip:** live LLM calls take 30 s–2 min. Kick off the slow ones and
> *talk* while they run — narrate the architecture, don't watch the spinner.

---

## The 10-minute run (click-path)

### 0:00 — Framing (30 s)
> "AI Career Co-Pilot is a privacy-first career assistant that runs 100% on this
> laptop — no cloud, no API keys, ₹0 running cost. It has five modules. The key
> idea: your resume and interview answers never leave the machine."

Open the **Home** dashboard — point at the cross-module stats.

### 0:30 — Resume Review (2 min)
1. **Review** tab → select the pre-loaded resume + JD → **Run review**.
2. While the stepper runs, explain: *"This is RAG — it retrieves the most
   relevant parts of my resume and the JD, injects them into the prompt, so the
   feedback is about my actual content, not generic."*
3. Show the report: **section critique**, a **bullet rewrite** (read one "before
   → after"), a **keyword gap**, and the **ATS checklist**.

### 2:30 — Interview + scoring (2 min)
1. **Interview** tab → **Generate questions** (or open a pre-made bank).
2. Start a mock interview, type one answer, **Finish**.
3. Show the **rubric scores** and say: *"Scoring runs at a low temperature so the
   same answer scores within one point on repeats — I'll come back to why that
   matters."*

### 4:30 — Voice moment (1 min, optional)
If configured: in an interview, switch to **Voice**, play a question (Piper),
record a one-line answer, transcribe (whisper.cpp). Then:
> "Notice the audio file is deleted the instant it's transcribed — only the text
> is kept."

### 5:30 — Roadmap (1.5 min)
1. **Roadmap** tab → target role "Backend Engineer" → **Generate** (or open a
   saved one).
2. Show the **skill-gap table** (current level judged from the resume, with the
   evidence line) and the **now / 3-month / 12-month** columns.
3. **Tick an action** → *"progress is saved instantly and survives a restart."*

### 7:00 — Outreach (1.5 min)
1. **Outreach** tab → open a contact → purpose *cold*, platform *LinkedIn note*,
   hook *"their talk on FastAPI"* → **Generate 3 variants**.
2. Show the **three tones**, the **character counter** (≤ 300), and **Copy**.
3. > "The app never sends anything — I copy it myself and mark it sent. And it
   > forces a specific hook so the message isn't a template."

### 8:30 — The privacy moment (1 min) 🔌
1. **Turn off Wi-Fi** (or unplug Ethernet) in front of the examiner.
2. Run one more action — e.g. reopen a review or generate a short outreach.
3. > "Still working, with no internet. The only time this app ever uses the
   > network is the one-time model download. This is the answer to *why not just
   > use ChatGPT* — I can't leak data that never leaves the disk."
4. Open **Settings** → show the single **SQLite path** and *"Delete ALL my data"*.

### 9:30 — Close (30 s)
> "Five modules, layered architecture, RAG, structured JSON output, 209
> automated tests plus a real-model evaluation harness — all local, all free."

Re-enable Wi-Fi.

---

## 15 likely viva questions — with strong answers

**1. Why not just use ChatGPT / a cloud API?**
Privacy and cost. A resume, salary expectations, and spoken interview answers are
highly sensitive; cloud tools upload them to third-party servers and usually
charge per use. This app processes everything locally through Ollama, so data
never leaves the machine and there's no recurring cost. I can *prove* it by
pulling the network cable mid-demo.

**2. How does RAG (Retrieval-Augmented Generation) work here?**
When a resume or JD is saved, I split it into chunks and embed each into a
768-dimension vector with `nomic-embed-text`, stored in a `sqlite-vec` table. At
generation time I embed the query, do a cosine-similarity search to pull the most
relevant chunks, and inject that text into the prompt. So the model reasons over
*my* actual content — that's why the feedback is specific, not generic.

**3. Why is the scoring consistent / how do you guarantee it?**
Two reasons. The scoring call runs at **temperature 0.2**, so sampling is nearly
deterministic — the same answer scores within ±1 point per dimension (verified in
the evaluation harness). And the session summary is computed **arithmetically**
from stored scores, not by another LLM call, so it can never contradict the
numbers it summarises.

**4. Why two different chat models?**
Model tiering for an 8 GB machine. `llama3.2:3b` handles reasoning-heavy tasks
(review, scoring, roadmap, outreach). Question-bank generation uses the faster
`llama3.2:1b` because those questions are templated and grounded enough that the
smaller model is sufficient, and it keeps generation near ~30 s. Both are under
4B parameters so they fit in RAM without a GPU.

**5. How do you get reliable JSON out of a small model?**
The Pydantic schema for each feature *is* the JSON schema I pass to Ollama's
`format` parameter, so generation is grammar-constrained to the right shape. If
validation still fails, the client does exactly one repair retry showing the
model its own error. For lists that a small model under-produces (e.g. "3
outreach variants") I set `minItems` in the schema, which the grammar enforces.

**6. What's your architecture?**
Four layers: a React SPA (presentation), a FastAPI orchestration layer with
Pydantic validation, an AI-services layer (prompt templates, RAG, scoring, the
Ollama client), and a data layer — one SQLite file with `sqlite-vec`. Long
operations stream progress over Server-Sent Events.

**7. Why SQLite and not PostgreSQL / a vector database like Pinecone?**
The whole product is single-user and local. SQLite is a single portable file
with zero setup, and `sqlite-vec` gives me vector search *inside that same file* —
so there's no separate database service to install or run, and no cloud vector DB
that would break the privacy guarantee.

**8. How is the app secure against SQL injection?**
Every query goes through SQLAlchemy, which parameterises statements by
construction. The few raw statements needed for the virtual table use bound
parameters (`:chunk_id`), never string formatting. So injection-safety is
structural, not something I have to remember per-query.

**9. What happens if Ollama is down or a model is missing?**
It's a reported state, never a crash. A global exception handler maps every
Ollama failure to friendly JSON `{message, hint}`, the frontend shows a toast
with the exact fix ("run: `ollama serve`" or "`ollama pull …`"), and the Setup
tab guides recovery. Streaming endpoints emit an `error` event instead of hanging.

**10. How does the voice feature protect privacy?**
whisper.cpp (STT) and Piper (TTS) run as local subprocesses — no cloud speech
API. The recorded WAV is written to a temp file, transcribed, and **deleted
immediately** in a `finally` block; only the transcript text persists. You can
watch `data/audio_tmp/` empty out after each answer.

**11. Why keep both `plan_json` and roadmap item rows?**
`plan_json` stores the model's original output verbatim — an evaluation baseline
for comparing prompt versions. The `RoadmapItem` rows are the user-editable copy,
so ticking one action is a single-row update instead of rewriting a whole JSON
blob. Regeneration matches new actions to old by text to carry over ticks.

**12. How do you enforce the LinkedIn 300-character limit if the model can't count?**
In code, after generation. Each platform has a hard limit; an over-long variant
is regenerated once with a focused "make it shorter" prompt, and if it's still
over, truncated at a sentence boundary. So the limit is guaranteed regardless of
what the model returns.

**13. How did you test an app whose core is a non-deterministic LLM?**
Two layers. Fast **integration tests** (209 of them) stub the Ollama client with
a mock HTTP transport, so they're deterministic and run in ~20 s — they verify
routing, validation, persistence, and error handling. Separately, a **real-model
evaluation harness** runs a fixed benchmark (5 resume/JD pairs, 5 outreach
scenarios) against the actual model and checks JSON validity, grounding, and
scoring consistency, producing a markdown results table.

**14. What are the limitations / what would you do next?**
On 8 GB CPU, generation is seconds-to-minutes, not instant — I mitigate with
streaming progress and model tiering. Quality is bounded by a 3B model. Next
steps: a job-description search/matching module, a larger model on better
hardware via the same settings switch, and a fine-tuned scoring model.

**15. What was the hardest engineering problem?**
Making long, silent LLM calls feel responsive on weak hardware without the
browser appearing frozen. A plain POST that stayed silent for two minutes got
severed by the dev-server proxy and looked stuck forever. I moved every long
operation to Server-Sent Events with live progress/heartbeats, which also made
errors recoverable mid-stream.

---

### One-line answers to keep in your pocket
- **Grounding:** "RAG injects my real resume/JD text into the prompt."
- **Consistency:** "Low temperature + arithmetic summaries."
- **Privacy:** "Loopback-only, local model, one-time download — I can prove it offline."
- **Reliability:** "Every failure is a friendly hint, never a stack trace."
