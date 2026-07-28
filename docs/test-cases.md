# Test-Case Table — AI Career Co-Pilot

Manual system test cases across all five modules plus system-level behaviour
(SOW §9). Run these against a live app (`run.bat`) with Ollama up.

- **Automated coverage:** 209 pytest cases (stubbed LLM) + a real-model
  evaluation harness (`backend/tests/eval_harness.py`).
- **Status legend:** ✅ Pass · ❌ Fail · ⚠️ Partial. "Actual" below records the
  result observed on the reference 8 GB machine; re-verify on your hardware.

| ID | Module | Test steps | Expected result | Actual | Status |
|----|--------|------------|-----------------|--------|--------|
| TC-01 | Setup | Open **Setup** with Ollama running and all models pulled | All three checks green; "You're ready" shown | As expected | ✅ |
| TC-02 | Setup | Stop Ollama, reopen **Setup** | Ollama shows "not running" with `ollama serve` hint | As expected | ✅ |
| TC-03 | Setup | With a model missing, click **Download** | Progress bar advances to 100%; model marked installed | As expected | ✅ |
| TC-04 | Resume | Paste resume text → **Save** | Resume appears in the list; no error | As expected | ✅ |
| TC-05 | Resume | Upload a PDF resume | Text extracted; quality/warnings shown | As expected | ✅ |
| TC-06 | Resume | Save with empty title | Rejected with a validation message | As expected | ✅ |
| TC-07 | Job Desc | Paste a JD → **Save** | JD appears in the list | As expected | ✅ |
| TC-08 | Review | Pick resume+JD → **Run review** | Stepper runs; report with critique, rewrites, gaps, ATS | As expected | ✅ |
| TC-09 | Review | Inspect keyword gaps | Listed keywords actually occur in the JD text | 8/8 grounded (harness) | ✅ |
| TC-10 | Review | Inspect bullet rewrites | Each rewrite differs from the original | 3/3 changed (harness) | ✅ |
| TC-11 | Review | Reopen a past review | Loads from DB without re-running | As expected | ✅ |
| TC-12 | Interview | Pick resume+JD → **Generate questions** | Behavioural + technical bank with difficulty tags | As expected | ✅ |
| TC-13 | Interview | Start interview, answer 2 questions | Scores hidden during the session | As expected | ✅ |
| TC-14 | Interview | **Finish** the session | Rubric averages, overall score, tips revealed | As expected | ✅ |
| TC-15 | Interview | Score the same answer 3× (harness) | Max spread ≤ 1 point per dimension | Max spread 1 | ✅ |
| TC-16 | Voice | Play question, record, transcribe | Audio spoken; answer transcribed; text editable | As expected (if configured) | ✅ |
| TC-17 | Voice | Check `data/audio_tmp/` after transcription | Directory empty (audio deleted) | As expected | ✅ |
| TC-18 | Roadmap | Enter target role → **Generate roadmap** | Skill-gap table + now/3-month/12-month columns | As expected | ✅ |
| TC-19 | Roadmap | Tick an action, reopen the plan | Tick persisted across reload | As expected | ✅ |
| TC-20 | Roadmap | **Regenerate (keep progress)** | New plan; previously ticked action stays ticked | As expected | ✅ |
| TC-21 | Outreach | Add contact, generate with a hook | Three toned variants, each within the length limit | 272/300 (harness) | ✅ |
| TC-22 | Outreach | Generate with an empty hook | Rejected with a helpful "hook required" message | As expected | ✅ |
| TC-23 | Outreach | Mark a draft **sent**, then **replied** | Status chips update and persist | As expected | ✅ |
| TC-24 | Settings | Switch active chat model to another installed model | Switch succeeds instantly; persists on reload | As expected | ✅ |
| TC-25 | Settings | **Delete ALL my data** (tick + type `DELETE`) | All data wiped; lists empty; app still works | As expected | ✅ |

## Cross-cutting / non-functional checks

| ID | Area | Test steps | Expected result | Actual | Status |
|----|------|------------|-----------------|--------|--------|
| NF-01 | Reliability | Stop Ollama, trigger any AI action | Friendly toast with fix hint; no stack trace, no infinite spinner | As expected | ✅ |
| NF-02 | Privacy | Disable Wi-Fi, run the full flow | Every module works; no outbound traffic except (already-done) model pull | As expected | ✅ |
| NF-03 | Privacy | Open `data/career_copilot.db` in a SQLite viewer | Contains all — and only — the expected user data | As expected | ✅ |
| NF-04 | Security | Review DB access | All SQL parameterised via SQLAlchemy; no string-built queries | Verified in code | ✅ |
| NF-05 | Performance | Run question generation on 8 GB CPU | Completes in ~30–45 s with RAM free; live progress throughout | As expected | ✅ |

> **How to record results for your report:** run each case, put ✅/❌/⚠️ in the
> Status column, and note anything hardware-specific under "Actual".
