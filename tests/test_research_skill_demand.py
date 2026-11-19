"""CCGE-151: demand mode checks that a segment's signal means construction work before picking it.

On 2026-11-18 a demand run picked newly registered dental practices, and 4 of the 6 researched
practices turned out to be already open in existing dental suites. These tests pin the skill text
that makes the pick rest on a sampled 'project conversion' rating and drops already-open prospects.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "research-prospects" / "SKILL.md"
VERSION = "1.3.0"
ALLOWED_TOOLS = [
    "WebSearch",
    "WebFetch",
    "Read(config/pilot.yaml)",
    "Read(cottonwood/schemas/research-record.schema.json)",
    "Write(out/research/**)",
]


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    """The body from a '## heading' line up to the next '## ' heading."""
    text = _text()
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _frontmatter() -> dict[str, object]:
    text = _text()
    end = text.index("\n---\n", 4)
    data = yaml.safe_load(text[4:end])
    assert isinstance(data, dict)
    return data


# --- AC 1: a sampled project-conversion rating that low or unknown never wins -------------


def test_demand_mode_rates_project_conversion_on_a_sample() -> None:
    demand = _section("Demand mode")
    assert "**project conversion**" in demand
    assert "in a sample of two or three organizations from the scan, does the signal mean" in demand
    assert "rather than a takeover, rebrand or move into an existing fitted-out space" in demand
    assert "Rate project conversion from that sample only" in demand


def test_low_or_unknown_project_conversion_never_wins() -> None:
    demand = _section("Demand mode")
    assert "A candidate rated `low` or `unknown` on project conversion never wins." in demand


# --- AC 2: the Procedure drops an already-open prospect and lists it under Dropped ---------


def test_procedure_drops_a_prospect_already_open_in_existing_space() -> None:
    procedure = _section("Procedure")
    assert (
        "Drop any prospect that is already open in an existing fitted-out space"
        " (a takeover, rebrand or move)" in procedure
    )
    assert '"now open"' in procedure
    assert "list it under **Dropped** in the demand report with the reason" in procedure


def test_already_open_check_comes_before_the_file_is_written() -> None:
    procedure = _section("Procedure")
    assert procedure.index("already open in an existing fitted-out space") < procedure.index(
        "Write the file"
    )


# --- AC 3: the demand report's shortlist has a Project conversion column -------------------


def test_demand_report_shortlist_has_a_project_conversion_column() -> None:
    output = _section("Output")
    shortlist = next(line for line in output.splitlines() if line.startswith("- **Shortlist:**"))
    assert "**Project conversion** column" in shortlist


# --- AC 4: version 1.3.0 in frontmatter and after-run step; allowed-tools unchanged --------


def test_version_is_1_3_0_in_frontmatter_and_after_run_step() -> None:
    assert _frontmatter()["version"] == VERSION
    assert f"--skill-version {VERSION}" in _section("After the run (the developer)")


def test_allowed_tools_are_unchanged() -> None:
    assert _frontmatter()["allowed-tools"] == ALLOWED_TOOLS
