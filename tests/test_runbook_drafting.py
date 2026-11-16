"""The runbook's drafting run: export, skill, recorded run, approval, gate, logged send."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "runbook.md"
HEADINGS = [
    "Restore from backup",
    "Re-applying suppression after a restore",
    "Deletion requests",
    "Inbound verification checklist",
    "Relay",
    "Research run",
    "Drafting run",
]
REQUIRED = [
    "cottonwood review --lead",
    "prepare-outreach",
    "cottonwood record-run --skill prepare-outreach",
    "cottonwood approve draft",
    "cottonwood prepare-send",
    "cottonwood log-outreach",
]


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def _section() -> str:
    text = _text()
    start = text.index("\n## Drafting run\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_drafting_run_follows_research_run() -> None:
    assert re.findall(r"^## (.+)$", _text(), re.M) == HEADINGS


def test_drafting_run_names_every_step_command() -> None:
    section = _section()
    for phrase in REQUIRED:
        assert phrase in section, phrase


def test_the_founder_sends_and_the_gate_is_not_bypassed() -> None:
    section = _section()
    assert "own mail client" in section
    assert "never edit `out/send/` by hand" in section
