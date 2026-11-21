# sir-target: tests/test_entry_option_problem.py
"""The log-time/log-cost option check is named for both of its jobs (F-maintainability-8)."""

from __future__ import annotations

import argparse

from cottonwood import cli


def _args(**given: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "amount": None,
        "date": None,
        "category": None,
        "estimated": None,
        "voids": None,
    }
    values.update(given)
    return argparse.Namespace(**values)


def test_the_old_name_is_gone() -> None:
    assert not hasattr(cli, "_void_entry_conflict")


def test_it_names_a_missing_required_option_without_voids() -> None:
    problem = cli._entry_option_problem(_args(amount="5", date="2026-11-16"), "amount")
    assert problem == "category: required unless --voids is given"


def test_it_names_an_entry_option_given_with_voids() -> None:
    problem = cli._entry_option_problem(_args(voids=3, estimated=True), "amount")
    assert problem == "voids: not allowed with estimated"


def test_a_complete_entry_or_a_bare_void_has_no_problem() -> None:
    full = _args(amount="5", date="2026-11-16", category="tools")
    assert cli._entry_option_problem(full, "amount") is None
    assert cli._entry_option_problem(_args(voids=3), "amount") is None
