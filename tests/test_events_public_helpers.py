# sir-target: tests/test_events_public_helpers.py
"""gate, claims and the approve command use the events helpers by their public names.

F-maintainability-2: they called events._insert_activity, _day_start, _voided_sql and
_parse_entry_date, so the contract those modules rely on was hidden behind private names.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from cottonwood import cli, events

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_USE = re.compile(r"events\._[a-z]")


@pytest.mark.parametrize(
    ("public", "private"),
    [
        ("insert_activity", "_insert_activity"),
        ("day_start", "_day_start"),
        ("voided_sql", "_voided_sql"),
        ("parse_entry_date", "_parse_entry_date"),
    ],
)
def test_each_public_name_is_the_helper(public: str, private: str) -> None:
    assert getattr(events, public) is getattr(events, private)


@pytest.mark.parametrize("module", ["cottonwood/gate.py", "cottonwood/claims.py"])
def test_gate_and_claims_call_no_private_events_name(module: str) -> None:
    source = (ROOT / module).read_text(encoding="utf-8")
    assert PRIVATE_USE.findall(source) == []


def test_the_approve_command_calls_no_private_events_name() -> None:
    source = inspect.getsource(cli._run_approve)
    assert "events.parse_entry_date(" in source
    assert PRIVATE_USE.findall(source) == []
