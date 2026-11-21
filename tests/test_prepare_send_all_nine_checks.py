# sir-target: tests/test_prepare_send_all_nine_checks.py
"""prepare-send names all nine failed checks, in the R-21 order, when every check fails.

F-testing-4 (review 20261115-191126): the every-failure test failed seven checks but left
suppression and claims passing, so a change that dropped or reordered either would pass.
"""

from __future__ import annotations

import json

import pytest
from test_prepare_send import (  # noqa: F401  (pytest fixtures)
    EMAIL,
    Setup,
    _assert_refused,
    _write_claims,
    fixed_now,
    ready,
)

from cottonwood.cli import EXIT_OK

ALL_NINE = [
    "approval",
    "eligibility",
    "suppression",
    "claims",
    "evidence",
    "sender_identity",
    "postal_address",
    "opt_out",
    "ad_identification",
]


def test_every_one_of_the_nine_checks_fails_and_is_named_in_order(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready.write_draft("Hello.\n")  # unapproved, and missing every configured value
    ready.sql("UPDATE contacts SET eligibility = 'ineligible' WHERE id = 1")
    assert ready.run("suppress", EMAIL, "--reason", "asked") == EXIT_OK
    _write_claims(ready, "unverified")
    ready.sql("UPDATE evidence SET observed_at = '2026-10-01'")

    lines = _assert_refused(ready, capsys, ALL_NINE)
    assert [line.split(":")[1].strip() for line in lines] == ALL_NINE
    assert all(line.startswith("refused: ") for line in lines)

    [refused] = ready.activities("prepare_refused")
    assert json.loads(refused["payload"])["checks"] == ALL_NINE
