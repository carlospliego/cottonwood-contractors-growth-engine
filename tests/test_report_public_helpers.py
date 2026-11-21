# sir-target: tests/test_report_public_helpers.py
"""report.py uses only public names from events and review (F-maintainability-1)."""

from __future__ import annotations

import ast
from pathlib import Path

from cottonwood import events, review

REPORT_SOURCE = Path(__file__).resolve().parents[1] / "cottonwood" / "report.py"


def _attributes_of(module_name: str) -> set[str]:
    tree = ast.parse(REPORT_SOURCE.read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == module_name
    }


def test_report_reads_no_private_events_names() -> None:
    used = _attributes_of("events")
    assert "entries_in_range" in used
    assert not {name for name in used if name.startswith("_")}


def test_report_reads_no_private_review_names() -> None:
    used = _attributes_of("review")
    assert "table_cell" in used
    assert not {name for name in used if name.startswith("_")}


def test_the_public_helpers_behave_as_before() -> None:
    assert review.table_cell(" a|b\nc ") == "a\\|b c"
    assert review.table_cell(None) == review.EMPTY
    assert callable(events.entries_in_range)
