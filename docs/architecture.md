# System Architecture — AI Career Co-Pilot

Academic design documentation (SOW §6, §10). All diagrams are Mermaid and render
in GitHub, VS Code, and most black-book tooling.

---

## 1. Architectural style

A **four-layer, locally-hosted web application**. The browser talks to a single
FastAPI backend, which orchestrates a local LLM (Ollama) and a single SQLite
file. Nothing is exposed to the network — both servers bind to `127.0.0.1`.

| Layer | Responsibility | Key code |
|-------|----------------|----------|
| **1 · Presentation** | React SPA; talks to the backend over REST + Server-Sent Events. No external CDNs. | `frontend/src/` |
| **2 · API / Orchestration** | FastAPI routers per module; Pydantic request/response validation; every LLM feature returns schema-validated JSON. | `backend/app/routers/`, `schemas/` |
| **3 · AI Services** | Prompt-template engine, RAG pipeline (chunk → embed → retrieve → inject), rubric scoring, and the Ollama client wrapper (retry, timeout, streaming). | `backend/app/services/`, `llm/` |
| **4 · Data & Local Runtimes** | SQLite via SQLAlchemy + `sqlite-vec` for embeddings. whisper.cpp & Piper as subprocesses. | `backend/app/models/`, `db.py` |

### Component diagram

```mermaid
flowchart TB
    subgraph Browser["Layer 1 — React SPA (127.0.0.1:5173)"]
        UI["Module pages:<br/>Review · Interview · Roadmap · Outreach · Dashboard"]
    end

    subgraph API["Layer 2 — FastAPI (127.0.0.1:8000)"]
        R["Routers<br/>(resume, review, interviews,<br/>roadmap, outreach, voice,<br/>setup, settings, stats)"]
        SCH["Pydantic schemas<br/>(also the JSON schema sent to Ollama)"]
    end

    subgraph SVC["Layer 3 — AI Services"]
        PROMPT["Prompt loader<br/>(versioned templates)"]
        RAG["RAG pipeline<br/>chunk-embed-retrieve-inject"]
        SCORE["Rubric scoring"]
        CLIENT["Ollama client<br/>(retry / timeout / stream)"]
    end

    subgraph DATA["Layer 4 — Data & Runtimes"]
        DB[("SQLite + sqlite-vec<br/>data/career_copilot.db")]
        VOICE["whisper.cpp · Piper<br/>(subprocess)"]
    end

    OLLAMA[["Ollama<br/>llama3.2:3b · 1b · nomic-embed-text"]]

    UI -->|REST + SSE| R
    R --> SCH
    R --> PROMPT & RAG & SCORE
    RAG --> CLIENT
    SCORE --> CLIENT
    CLIENT -->|HTTP 127.0.0.1:11434| OLLAMA
    RAG --> DB
    R --> DB
    R --> VOICE
```

---

## 2. Data-Flow Diagram — Level 0 (context)

The whole system as one process, showing what crosses the boundary. Only the
**one-time model download** ever touches the internet.

```mermaid
flowchart LR
    User([User])
    System((("AI Career Co-Pilot System")))
    Ollama[["Ollama (local LLM runtime)"]]
    Net{{"Internet (one-time only)"}}

    User -->|"resume, job description, interview answers, contact + hook"| System
    System -->|"critique, questions & scores, roadmap, message drafts"| User
    System <-->|"prompts / completions (local HTTP)"| Ollama
    Net -.->|"one-time model pull"| Ollama
```

---

## 3. Data-Flow Diagram — Level 1

The system decomposed into processes and data stores. Every arrow stays on the
machine except the dashed one-time pull.

```mermaid
flowchart TB
    User([User])
    Ollama[["Ollama LLM"]]

    P1(("1.0 Ingest and Index"))
    P2(("2.0 Resume Review"))
    P3(("3.0 Interview and Scoring"))
    P4(("4.0 Roadmap"))
    P5(("5.0 Outreach"))

    D1[("D1 · Resumes / JDs")]
    D2[("D2 · Embeddings (sqlite-vec)")]
    D3[("D3 · Reviews")]
    D4[("D4 · Interview sessions & turns")]
    D5[("D5 · Roadmaps")]
    D6[("D6 · Contacts & drafts")]

    User -->|resume / JD text| P1
    P1 -->|rows| D1
    P1 -->|chunks + vectors| D2

    User -->|choose resume + JD| P2
    D1 --> P2
    D2 -->|retrieved context| P2
    P2 <-->|critique / rewrites / gaps| Ollama
    P2 --> D3
    D3 -->|report| User

    User -->|start interview| P3
    D1 --> P3
    P3 <-->|questions / scores| Ollama
    P3 --> D4
    D4 -->|summary & trend| User

    User -->|target role| P4
    D1 --> P4
    D2 --> P4
    P4 <-->|skill gap / plan| Ollama
    P4 --> D5
    D5 -->|editable plan| User

    User -->|contact + hook| P5
    D1 --> P5
    P5 <-->|3 variants| Ollama
    P5 --> D6
    D6 -->|drafts + status| User
```

---

## 4. Use-Case Diagram

```mermaid
flowchart LR
    User((User))

    subgraph System["AI Career Co-Pilot"]
        UC1(["Ingest resume / JD"])
        UC2(["Review & tailor resume"])
        UC3(["Generate question bank"])
        UC4(["Run scored mock interview"])
        UC5(["Practise by voice"])
        UC6(["Generate skill-gap roadmap"])
        UC7(["Track roadmap progress"])
        UC8(["Draft outreach messages"])
        UC9(["Track outreach status"])
        UC10(["View dashboard"])
        UC11(["Configure models / delete data"])
    end

    Ollama((Ollama))
    Voice((whisper.cpp / Piper))

    User --- UC1 & UC2 & UC3 & UC4 & UC5
    User --- UC6 & UC7 & UC8 & UC9 & UC10 & UC11

    UC2 -.->|uses| Ollama
    UC3 -.->|uses| Ollama
    UC4 -.->|uses| Ollama
    UC6 -.->|uses| Ollama
    UC8 -.->|uses| Ollama
    UC5 -.->|uses| Voice
```

---

## 5. Request lifecycle — a streamed review (representative sequence)

Long AI operations stream progress as Server-Sent Events so the UI never looks
frozen. This is the same pattern used by review, roadmap, outreach, and question
generation.

```mermaid
sequenceDiagram
    participant U as Browser
    participant A as FastAPI router
    participant S as review_service
    participant E as Ollama (embed)
    participant C as Ollama (chat)
    participant DB as SQLite

    U->>A: POST /api/review (resume_id, jd_id)
    A-->>U: 200, text/event-stream
    A->>S: generate_review()
    S->>E: embed queries (retrieval)
    E-->>S: vectors
    S->>DB: vector search - relevant chunks
    S-->>U: event step (retrieve done)
    S->>C: critique prompt (JSON schema)
    C-->>S: validated JSON
    S-->>U: event step (critique done)
    Note over S,C: rewrites - keyword gap - ATS
    S->>DB: persist report
    S-->>U: event done (report_id, report)
```

---

## 6. Design principles (defensible in the viva)

- **Privacy by architecture** — loopback-only binding; the only outbound call is
  the one-time model pull. This is a structural guarantee, not a policy.
- **Grounded, not generic** — RAG injects the user's actual resume/JD text into
  every prompt, so outputs cite real content (SOW §6.2).
- **Structured output** — Pydantic models *are* the JSON schema handed to Ollama,
  so the model is constrained to valid output; one repair retry handles the rest.
- **Determinism where it matters** — scoring runs at temperature 0.2 for ±1-point
  repeatability; summaries are computed arithmetically, not by the model.
- **Model tiering** — `llama3.2:3b` for reasoning, `llama3.2:1b` for fast question
  generation, `nomic-embed-text` for retrieval; all under 4B for an 8 GB machine.
- **Graceful degradation** — a down Ollama, a missing model, or absent voice
  binaries are reported states with fix hints, never crashes.
