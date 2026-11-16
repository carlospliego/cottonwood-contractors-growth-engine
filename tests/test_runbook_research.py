"""The runbook's research-run routine: skill, check, import, /cost, record-run (R-25, R-26)."""

from __future__ import annotations

import re
from pathlib import Path

RUNBOOK = Path(__file__).resolve().parent.parent / "docs" / "runbook.md"
_STEP = re.compile(r"^\d+\. ", re.MULTILINE)


def _section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.index("\n## Research run\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _steps() -> list[str]:
    section = _section()
    starts = [match.start() for match in _STEP.finditer(section)]
    return [section[a:b] for a, b in zip(starts, [*starts[1:], len(section)], strict=True)]


def _first_step(predicate: str, *, without: str | None = None) -> int:
    for number, step in enumerate(_steps()):
        if predicate in step and (without is None or without not in step):
            return number
    raise AssertionError(f"no step mentions {predicate!r}")


def test_research_run_steps_are_in_order() -> None:
    skill = _first_step("research-prospects")
    check = _first_step("--check")
    assert "prospects-import" in _steps()[check]
    imported = _first_step("prospects-import", without="--check")
    cost = _first_step("/cost")
    record = _first_step("record-run")
    assert skill < check < imported < cost <= record
    assert "--cost-source claude-code-cost" in _steps()[record]


def test_inexact_cost_uses_the_billing_console_marked_estimated() -> None:
    section = _section()
    assert "billing-console" in section
    assert "--estimated" in section
    line = next(line for line in section.splitlines() if "billing-console" in line)
    assert "--estimated" in line
