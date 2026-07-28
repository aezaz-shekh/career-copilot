# Versioned Prompt Templates

Every LLM feature loads its instructions from a plain-text file in this folder
rather than from a Python string. This is deliberate: SOW §7 (Maintainability)
requires *versioned prompt templates*, and §9 requires the evaluation harness to
compare output quality across prompt revisions.

## Naming convention

    <module>_<task>_v<N>.txt

Examples:

    resume_critique_v1.txt
    resume_bullet_rewrite_v1.txt
    interview_question_bank_v1.txt
    interview_answer_scoring_v1.txt
    roadmap_skill_gap_v1.txt
    outreach_draft_v1.txt

## Rules

1. **Never edit a released version in place.** Copy it to `_v2` and change that,
   so evaluation-harness results stay reproducible against the prompt they used.
2. Each scoring prompt must state the exact JSON shape it has to return; the
   response is validated against a Pydantic schema in `backend/app/schemas/`.
3. Placeholders use `string.Template` style with a `$` prefix: `$resume_text`,
   `$jd_text`. **Not** `str.format` — these templates describe JSON, and
   `str.format` treats every `{` in a JSON example as a field reference and
   raises. Substitution is `safe_substitute`, so a stray `$` in a user's resume
   cannot break generation.
4. Keep few-shot examples short — every example token costs latency on a 3B
   CPU-only model.

## Loading

`app/llm/prompts.py` resolves a bare name to the **highest** available version,
so application code says `render_prompt("resume_parser", resume_text=...)` and a
new revision goes live simply by adding `resume_parser_v2.txt`. Pass
`version=1` to pin an old one — which is what the evaluation harness does when
comparing revisions.

## Current templates

Source: Prompt Playbook Section C. Placeholders were converted from the
playbook's `{name}` to `string.Template`'s `$name` (see rule 3 above) — the
JSON braces in each template stay literal, which is the whole reason for the
`$` convention. Each is wired up in the phase noted below.

| Name | Placeholders | Wired up in |
|---|---|---|
| `resume_parser_v1.txt` | `$resume_text` | Phase 1 — **active** (pinned) |
| `resume_parser_v2.txt` | `$resume_text` | evaluation only (measured worse) |
| `section_critique_v1.txt` | `$jd_chunks` `$resume_chunks` | Phase 1 (critique) |
| `bullet_rewrite_v1.txt` | `$jd_chunks` `$bullets_json` | Phase 1 (critique) |
| `keyword_gap_v1.txt` | `$jd_chunks` `$resume_chunks` | Phase 1 (critique) |
| `question_gen_v1.txt` | `$n_behavioral` `$n_technical` `$jd_chunks` `$resume_chunks` | Phase 2 |
| `answer_scoring_v1.txt` | `$question` `$jd_chunks` `$answer` | Phase 2 |
| `followup_decider_v1.txt` | `$question` `$answer` | Phase 2 |
| `skill_gap_v1.txt` | `$target_role` `$resume_chunks` | Phase 3 |
| `roadmap_v1.txt` | `$target_role` `$gaps_json` | Phase 3 |
| `outreach_draft_v1.txt` | `$purpose` `$platform` `$char_limit` `$contact_json` `$hook` `$resume_chunks` `$target_role` | Phase 3a |

> **resume_parser note:** the playbook's C1 uses different JSON keys
> (`title`, `year`, `tech`) than the enforced `ParsedResume` schema
> (`role`, `start_date`/`end_date`, `technologies`). Since the schema is passed
> to Ollama's `format` parameter, output is constrained to the schema's keys
> regardless of the prompt. The active v1 template is written to match the
> schema; it was not overwritten with C1.

> **Temperatures** (from the playbook): `answer_scoring` runs at 0.2 (scoring
> must be consistent) and `outreach_draft` at 0.7 (creative). These are applied
> by the calling service, not stored in the template.

## Measured comparison: resume_parser v1 vs v2

Same input (the seeded sample resume, rendered to PDF and extracted with
PyMuPDF, 1,742 characters), same model `llama3.2:3b`, temperature 0.2.

v2 was written specifically to fix v1 missing the EXPERIENCE section. It did —
and regressed three other fields in the process.

| Field | Truth | v1 | v2 |
|---|---|---|---|
| contact.name | Aarav Sharma | ✗ null | ✓ |
| contact.email | aarav.sharma@example.com | ✓ | ✗ returned the phone number |
| skills | 15 | ✓ 15 | ✓ 15 |
| experience | 1 internship | ✗ 0 | ~ 2 (1 correct, 1 project misfiled) |
| education | 1 | ✓ | ✓ |
| projects | 3 | ✓ 3 | ✗ 0 |
| certifications | 1 | ✓ | ✗ 0 |
| **Fields correct** | | **5 / 7** | **3 / 7** |
| Generation time | | 117 s | 151 s |

**Conclusion:** v1 stays active, pinned in
`app/services/resume_service.py::PROMPT_VERSION`. v2 is kept in the repository
as evidence, not deleted — the Phase 5 evaluation harness needs both to
reproduce this table.

**What this demonstrates for the report:** on a 3B model, prompt edits move
errors around rather than removing them. Strengthening one instruction stole
attention from others. This is the concrete justification for two SOW
decisions: the mandatory manual-edit step (§11) and the evaluation harness (§9).
Prompt quality has to be *measured*, because intuition about what will help is
unreliable at this model size.

**If more accuracy is needed later**, the promising direction is architectural
rather than more prompt tweaking: split structuring into two smaller calls
(contact/summary/skills, then experience/education/projects) so the model holds
less in view at once. The cost is roughly double the latency, which is why it
was not done in Phase 1.
