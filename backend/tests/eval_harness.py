"""LLM evaluation harness (Phase 5, Prompt 5.1) — the SOW's headline enterprise
feature (Section 9): a fixed benchmark run against the *real* local model and
scored for specificity, JSON-schema validity, and scoring consistency.

This is NOT a pytest test — it needs Ollama running and takes several minutes on
CPU, so it is run by hand and its filename deliberately avoids the ``test_``
prefix (pytest won't collect it).

    cd backend
    .venv\\Scripts\\python.exe tests\\eval_harness.py            # full benchmark
    .venv\\Scripts\\python.exe tests\\eval_harness.py --limit 1   # quick smoke run

It loads 5 resume/JD pairs and 5 outreach scenarios from tests/fixtures/, runs
the real pipelines, and writes a markdown results table to backend/eval_results.md
that can be pasted straight into the project report.

Checks performed:
  * Resume review returns schema-valid JSON (a raised error = a fail).
  * Keyword-gap items are grounded — they actually occur in the JD text.
  * Bullet rewrites differ from the originals (not echoed back).
  * Outreach variants respect the per-platform character limits.
  * Scoring consistency — the same answer scored 3x, max spread <= 1 per dimension.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Allow `python tests/eval_harness.py` from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import create_db_engine, init_db  # noqa: E402
from app.models import Contact, JobDescription, ResumeVersion  # noqa: E402
from app.models.base import SourceType  # noqa: E402
from app.schemas.interview import RUBRIC_DIMENSIONS  # noqa: E402
from app.schemas.outreach import PLATFORM_CHAR_LIMITS  # noqa: E402
from app.services import (  # noqa: E402
    indexing,
    interview_service,
    outreach_service,
    review_service,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def log(msg: str) -> None:
    """Progress to stderr, so it doesn't pollute the markdown on stdout."""
    print(msg, file=sys.stderr, flush=True)


def _grounded(keyword: str, haystack: str) -> bool:
    """A keyword is 'grounded' if it — or a meaningful word of it — is in the JD."""
    k = keyword.lower().strip()
    if k and k in haystack:
        return True
    return any(len(word) > 3 and word in haystack for word in k.split())


# --------------------------------------------------------------------------- #
# Individual evaluations
# --------------------------------------------------------------------------- #


async def eval_review(session: Session, pair: dict) -> dict:
    """Index a resume+JD, run the real review, and score the output."""
    r = pair["resume"]
    resume = ResumeVersion(title=r["title"], raw_text=r["raw_text"], parsed_json=r["parsed"])
    session.add(resume)
    jd_data = pair["jd"]
    jd = JobDescription(
        title=jd_data["title"], company=jd_data.get("company"), raw_text=jd_data["raw_text"]
    )
    session.add(jd)
    session.commit()
    session.refresh(resume)
    session.refresh(jd)

    await indexing.index_document(session, SourceType.RESUME, resume.id, resume.raw_text)
    await indexing.index_document(session, SourceType.JD, jd.id, jd.raw_text)

    report = None
    async for event in review_service.generate_review(session, resume, jd):
        if event.stage == "complete":
            report = event.report

    if report is None:
        return {"role": pair["role"], "json_valid": False}

    jd_low = jd_data["raw_text"].lower()
    rewrites = report.rewrites
    diff = sum(
        1 for rw in rewrites if rw.improved.strip() and rw.improved.strip() != rw.original.strip()
    )
    gaps = report.gaps
    grounded = sum(1 for g in gaps if _grounded(g.keyword, jd_low))

    return {
        "role": pair["role"],
        "json_valid": True,
        "sections": len(report.sections),
        "rewrites_total": len(rewrites),
        "rewrites_diff": diff,
        "gaps_total": len(gaps),
        "gaps_grounded": grounded,
        "ats": f"{report.ats.passed_count}/{report.ats.total}",
    }


async def eval_outreach(session: Session, sender: ResumeVersion, scenario: dict) -> dict:
    """Generate the three variants for one scenario and check the length limits."""
    contact = Contact(**scenario["contact"])
    session.add(contact)
    session.commit()
    session.refresh(contact)

    platform = scenario["platform"]
    variants = await outreach_service.create_outreach_drafts(
        session,
        contact,
        sender,
        scenario["target_role"],
        purpose=scenario["purpose"],
        platform=platform,
        hook=scenario["hook"],
    )
    limit = PLATFORM_CHAR_LIMITS[platform]
    lengths = [len(v.text) for v in variants]
    return {
        "name": scenario["name"],
        "platform": platform,
        "variants": len(variants),
        "within_limit": all(n <= limit for n in lengths),
        "max_chars": max(lengths) if lengths else 0,
        "limit": limit,
    }


async def eval_scoring(fixture: dict, runs: int = 3) -> dict:
    """Score the same answer `runs` times; report the spread per rubric dimension."""
    results = []
    for i in range(runs):
        log(f"    scoring run {i + 1}/{runs}…")
        scoring, _ = await interview_service.score_answer(
            fixture["question"], fixture["answer"], fixture["jd_context"]
        )
        results.append(scoring.scores.model_dump())

    spreads = {
        dim: max(r[dim] for r in results) - min(r[dim] for r in results)
        for dim in RUBRIC_DIMENSIONS
    }
    return {"runs": results, "spreads": spreads, "max_spread": max(spreads.values())}


# --------------------------------------------------------------------------- #
# Markdown report
# --------------------------------------------------------------------------- #


def build_markdown(reviews: list[dict], outreach: list[dict], scoring: dict | None) -> str:
    lines: list[str] = []
    lines.append("# AI Career Co-Pilot — Evaluation Results")
    lines.append("")
    lines.append(
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} against the local model._"
    )
    lines.append("")

    # Review table
    lines.append("## 1. Resume Review (5 resume/JD pairs)")
    lines.append("")
    lines.append(
        "| Role | JSON valid | Sections | Rewrites changed | Gap keywords grounded | ATS |"
    )
    lines.append(
        "|------|:----------:|:--------:|:----------------:|:---------------------:|:---:|"
    )
    for r in reviews:
        if not r.get("json_valid"):
            lines.append(f"| {r['role']} | ❌ | — | — | — | — |")
            continue
        lines.append(
            f"| {r['role']} | ✅ | {r['sections']} | "
            f"{r['rewrites_diff']}/{r['rewrites_total']} | "
            f"{r['gaps_grounded']}/{r['gaps_total']} | {r['ats']} |"
        )
    lines.append("")

    # Outreach table
    lines.append("## 2. Outreach Drafts (5 scenarios)")
    lines.append("")
    lines.append("| Scenario | Platform | Variants | Within limit | Max chars / limit |")
    lines.append("|----------|----------|:--------:|:------------:|:-----------------:|")
    for o in outreach:
        mark = "✅" if o["within_limit"] else "❌"
        lines.append(
            f"| {o['name']} | {o['platform']} | {o['variants']} | {mark} | "
            f"{o['max_chars']}/{o['limit']} |"
        )
    lines.append("")

    # Scoring table
    if scoring is not None:
        lines.append("## 3. Scoring Consistency (same answer × 3)")
        lines.append("")
        header = "| Dimension | " + " | ".join(f"Run {i + 1}" for i in range(len(scoring["runs"])))
        header += " | Spread | Pass (≤1) |"
        lines.append(header)
        lines.append(
            "|-----------|" + "|".join([":---:"] * len(scoring["runs"])) + "|:------:|:---------:|"
        )
        for dim in RUBRIC_DIMENSIONS:
            cells = " | ".join(str(run[dim]) for run in scoring["runs"])
            spread = scoring["spreads"][dim]
            passed = "✅" if spread <= 1 else "❌"
            lines.append(f"| {dim} | {cells} | {spread} | {passed} |")
        lines.append("")
        overall = "✅ PASS" if scoring["max_spread"] <= 1 else "❌ FAIL"
        lines.append(
            f"**Overall scoring consistency (max spread {scoring['max_spread']}): {overall}**"
        )
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


async def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    pair_files = sorted((FIXTURES / "pairs").glob("*.json"))
    scenarios_doc = json.loads((FIXTURES / "outreach_scenarios.json").read_text(encoding="utf-8"))
    scoring_fx = json.loads((FIXTURES / "scoring_answer.json").read_text(encoding="utf-8"))
    if limit is not None:
        pair_files = pair_files[:limit]
        scenarios_doc["scenarios"] = scenarios_doc["scenarios"][:limit]

    # A throwaway database so the benchmark never touches the user's real data.
    tmp = Path(tempfile.mkdtemp(prefix="eval_")) / "eval.db"
    engine = create_db_engine(f"sqlite:///{tmp}")
    init_db(engine)

    reviews: list[dict] = []
    outreach_results: list[dict] = []
    scoring_result: dict | None = None

    with Session(engine) as session:
        for i, pf in enumerate(pair_files, 1):
            pair = json.loads(pf.read_text(encoding="utf-8"))
            log(f"[{i}/{len(pair_files)}] Review — {pair['role']} …")
            try:
                reviews.append(await eval_review(session, pair))
            except Exception as exc:  # noqa: BLE001 - one bad pair shouldn't abort the run
                log(f"    review failed: {exc}")
                reviews.append({"role": pair["role"], "json_valid": False})

        # One sender profile for all outreach scenarios.
        sender_data = scenarios_doc["sender_resume"]
        sender = ResumeVersion(title=sender_data["title"], raw_text=sender_data["raw_text"])
        session.add(sender)
        session.commit()
        session.refresh(sender)

        for i, scenario in enumerate(scenarios_doc["scenarios"], 1):
            log(f"[{i}/{len(scenarios_doc['scenarios'])}] Outreach — {scenario['name']} …")
            try:
                outreach_results.append(await eval_outreach(session, sender, scenario))
            except Exception as exc:  # noqa: BLE001
                log(f"    outreach failed: {exc}")
                outreach_results.append(
                    {
                        "name": scenario["name"],
                        "platform": scenario["platform"],
                        "variants": 0,
                        "within_limit": False,
                        "max_chars": 0,
                        "limit": PLATFORM_CHAR_LIMITS[scenario["platform"]],
                    }
                )

        log("Scoring consistency (3 runs)…")
        try:
            scoring_result = await eval_scoring(scoring_fx)
        except Exception as exc:  # noqa: BLE001
            log(f"    scoring failed: {exc}")

    engine.dispose()

    markdown = build_markdown(reviews, outreach_results, scoring_result)
    out_path = Path(__file__).resolve().parents[1] / "eval_results.md"
    out_path.write_text(markdown, encoding="utf-8")

    print(markdown)  # stdout: the pasteable table
    log(f"\nResults written to {out_path}")


if __name__ == "__main__":
    # Windows consoles default to cp1252, which can't encode the ✅/❌ in the
    # table; force UTF-8 so the pasteable markdown prints without crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
