# User Manual — AI Career Co-Pilot

A step-by-step guide to every module. Everything below runs entirely on your
machine; nothing is uploaded anywhere.

**Before you start:** make sure `ollama serve` is running and the three models
are installed (the **Setup** tab checks this and can download them for you).
Open the app at <http://127.0.0.1:5173>.

The top navigation has: **Home · Resume · Job Description · Review · Interview ·
Roadmap · Outreach · Setup · Settings · Status**.

---

## 0. First run — the Setup tab

1. Open **Setup**. It shows three checks:
   - **Ollama runtime** — green when reachable.
   - **Required models** — each of `llama3.2:3b`, `llama3.2:1b`,
     `nomic-embed-text`. If one is missing, click **Download** and watch the
     progress bar. This is the only step that needs the internet.
   - **Voice (optional)** — "installed" or "optional, not configured".
2. When it says **"You're ready — all models installed"**, you're set.

> **Tip:** The little coloured dot on the Setup/Status tabs is amber when
> something needs attention, green when everything's ready.

---

## 1. Resume Review & Tailoring

**Goal:** turn a generic resume into one tailored to a specific job.

1. **Resume** tab → paste your resume text (or upload a PDF) → **Save**. The app
   extracts the text and (optionally) structures it into sections.
2. **Job Description** tab → paste the target JD → **Save**.
3. **Review** tab → pick the resume and JD → **Run review**.
4. Watch the stepper: *retrieve → critique → rewrites → keyword gap → ATS*.
5. Read the report:
   - **Section critique** — strengths and specific issues with fixes.
   - **Bullet rewrites** — stronger versions of your experience bullets, with
     *why* each is better for this JD.
   - **Keyword gaps** — skills the JD wants that your resume is missing.
   - **ATS checklist** — formatting checks an applicant-tracking system cares about.

> **Tips:** Reviews are saved — reopen a past one instead of re-running (which
> costs minutes again). The rewrites never invent achievements; they sharpen
> what you already wrote.

---

## 2. Interview Prep & Mock Interviews

**Goal:** rehearse with questions grounded in *your* resume and *this* job.

1. **Interview** tab → pick a resume and JD → **Generate questions**.
   - A live counter shows elapsed seconds (generation uses the fast 1B model).
2. Browse the **question bank** — filter by type (behavioural/technical) and
   difficulty. Each question shows what a good answer demonstrates.
3. Click **Start Mock Interview**.
4. Answer each question (type your response). Scores are **hidden during** the
   interview — just like a real one.
5. Click **Finish** to reveal the summary: per-dimension rubric averages
   (structure, specificity, STAR method, relevance), an overall score, strengths,
   and improvement tips.

> **Tips:** Use the STAR structure (Situation, Task, Action, Result) — the rubric
> rewards it. Past interviews are saved under "Past interviews" for replay.

---

## 3. Voice Mock Interviews (optional)

**Goal:** practise *speaking* your answers.

*Requires whisper.cpp + Piper installed — see [voice-setup.md](voice-setup.md).*

1. Start a mock interview as above. If voice is configured, a **Text / Voice**
   toggle appears.
2. Switch to **Voice**:
   - **Play** the question (Piper speaks it aloud).
   - **Record** your spoken answer, then **Stop**.
   - The answer is transcribed locally (whisper.cpp); edit the transcript if
     needed, then **Submit**.
3. Scoring is identical to text mode — the same rubric.

> **Privacy tip:** your recorded audio is deleted the moment it's transcribed;
> only the text is kept. Check `data/audio_tmp/` — it's empty afterward.

---

## 4. Career Path & Skill-Gap Guidance

**Goal:** see the gap to a target role and a concrete plan to close it.

1. **Roadmap** tab → pick a resume, type a **target role** (e.g. "Backend
   Engineer") → **Generate roadmap**.
2. Read the **skill-gap table**: each skill shows your current level (judged from
   your resume, with the evidence line), the required level, the gap, and priority.
3. Read the **roadmap** — three columns:
   - **Now** (0–1 month), **3-Month** (1–3 months), **12-Month** (3–12 months).
   - Each action has a type (course/project/cert/practice) and a *why*.
4. **Tick actions** as you complete them — progress saves instantly.
5. **Regenerate (keep my progress)** reruns the plan while preserving your ticks.

> **Tips:** Actions are described generically ("complete a SQL course covering
> joins and indexing") — never paid product names. Your roadmap survives app
> restarts; reopen it any time from "Saved roadmaps".

---

## 5. Networking / Outreach Drafter

**Goal:** write a personal, non-templated message to a real person.

1. **Outreach** tab → add a **contact** (name, role, company, and a note/hook).
   Everything is typed by hand — nothing is scraped.
2. Select the contact → choose a **purpose** (cold / referral / thank-you /
   follow-up) and a **platform** (LinkedIn note / InMail / email).
3. Type a **hook** — one specific detail about the person (their talk, a project,
   a shared interest). **This is required** — it's what stops the message reading
   like a template.
4. **Generate 3 variants** — three tones (concise-formal / warm / direct),
   grounded in your resume and target role. Each respects the platform's length
   limit (LinkedIn ≤ 300 chars).
5. **Copy** the one you like into LinkedIn or Gmail yourself. Then mark it
   **sent**, and later **replied** — the status chips track your outreach.

> **Tips:** The app never sends anything for you (by design). A great hook is the
> single biggest quality lever — be specific.

---

## The Home dashboard

The **Home** tab summarises everything at a glance: number of resumes, your
interview score trend (a small chart), roadmap completion %, and outreach reply
rate. It updates as you use the other modules.

---

## Settings

- **Active chat model** — switch to any model you've installed (instant, no
  restart). Question generation and embeddings keep their tuned models.
- **Where my data lives** — the exact path to your single SQLite file, and its size.
- **Delete ALL my data** — wipes everything after you tick the box *and* type
  `DELETE`. Use this before handing the machine to someone else.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Red toast "Ollama is not running" | Run `ollama serve` in a terminal. |
| Toast about a missing model | **Setup** tab → **Download**, or `ollama pull <name>`. |
| "Can't reach the backend" | Make sure `uvicorn` is running on port 8000. |
| Generation feels stuck | It's slow, not stuck — watch the live progress. Close spare apps to free RAM. |
| Browser "refused to connect" | The frontend (port 5173) isn't running — start it, or use `run.bat`. |
