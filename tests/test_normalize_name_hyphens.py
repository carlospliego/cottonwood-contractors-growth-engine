# sir-target: tests/test_normalize_name_hyphens.py
"""normalize_name keeps word boundaries at hyphens and drops apostrophes (F-correctness-5)."""

from __future__ import annotations

from cottonwood.normalize import normalize_name


def test_hyphenated_and_spaced_names_match() -> None:
    assert normalize_name("Mary-Jane Smith") == normalize_name("Mary Jane Smith")
    assert normalize_name("Mary-Jane Smith") == "mary jane smith"


def test_apostrophes_are_removed_not_spaced() -> None:
    assert normalize_name("O'Neil") == "oneil"
    assert normalize_name("O’Neil") == "oneil"


def test_other_punctuation_collapses_to_single_spaces() -> None:
    assert normalize_name("  Jane   O'Neil, Jr. ") == "jane oneil jr"
    assert normalize_name("Smith/Jones & Co.") == "smith jones co"
