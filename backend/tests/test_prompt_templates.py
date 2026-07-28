"""Guard tests for every prompt template in prompts/.

These catch the mistakes that would otherwise only surface at generation time,
minutes into a slow local run: a template that still uses `{name}` fillers
instead of `$name`, a placeholder the calling code forgot to provide, or a
JSON example accidentally mangled into a template variable.
"""

from __future__ import annotations

from string import Template

import pytest

from app.llm.prompts import load_prompt, prompts_dir, render_prompt

# name -> the exact set of placeholders the template must expose.
# This table is the contract between each prompt file and the code that fills it
# (Prompt Playbook Section C). If a template drifts, one of these fails.
EXPECTED_PLACEHOLDERS: dict[str, set[str]] = {
    "resume_parser": {"resume_text"},
    "section_critique": {"jd_chunks", "resume_chunks"},
    "bullet_rewrite": {"jd_chunks", "bullets_json"},
    "keyword_gap": {"jd_chunks", "resume_chunks"},
    "question_gen": {"n_behavioral", "n_technical", "jd_chunks", "resume_chunks"},
    "answer_scoring": {"question", "jd_chunks", "answer"},
    "followup_decider": {"question", "answer"},
    "skill_gap": {"target_role", "resume_chunks"},
    "roadmap": {"target_role", "gaps_json"},
    "outreach_draft": {
        "purpose",
        "platform",
        "char_limit",
        "contact_json",
        "hook",
        "resume_chunks",
        "target_role",
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED_PLACEHOLDERS))
def test_template_exposes_exactly_its_expected_placeholders(name: str) -> None:
    template = Template(load_prompt(name))
    assert set(template.get_identifiers()) == EXPECTED_PLACEHOLDERS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_PLACEHOLDERS))
def test_template_renders_with_no_placeholders_left(name: str) -> None:
    values = {key: f"<{key}>" for key in EXPECTED_PLACEHOLDERS[name]}
    rendered = render_prompt(name, **values)

    # Every declared placeholder was substituted...
    for key in EXPECTED_PLACEHOLDERS[name]:
        assert f"<{key}>" in rendered
    # ...and nothing that looks like an unfilled $identifier survives.
    assert set(Template(rendered).get_identifiers()) == set()


# resume_parser describes its output shape in prose (the schema is enforced via
# Ollama's `format` parameter), so it has no literal JSON braces. Every Section C
# template embeds a JSON example instead.
_EMBEDS_JSON = sorted(set(EXPECTED_PLACEHOLDERS) - {"resume_parser"})


@pytest.mark.parametrize("name", _EMBEDS_JSON)
def test_template_still_contains_its_json_braces(name: str) -> None:
    """The JSON output spec must survive rendering (the point of using $-style)."""
    rendered = render_prompt(name, **{key: "x" for key in EXPECTED_PLACEHOLDERS[name]})
    assert "{" in rendered and "}" in rendered
    assert "Output ONLY valid JSON" in rendered


def test_no_template_uses_brace_style_fillers() -> None:
    """A leftover {resume_text}-style filler would never be substituted."""
    import re

    # A single-word lowercase token in braces with no quotes/colon is a filler,
    # not JSON (JSON keys here are always quoted, e.g. {"scores":...}).
    filler = re.compile(r"\{[a-z_]+\}")
    for path in prompts_dir().glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        leftovers = filler.findall(text)
        assert not leftovers, f"{path.name} has brace-style fillers: {leftovers}"


def test_all_expected_templates_exist_on_disk() -> None:
    for name in EXPECTED_PLACEHOLDERS:
        # Does not raise -> a v1 (or bare) file exists.
        assert load_prompt(name)
