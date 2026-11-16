# sir-target: tests/test_prepare_send_no_overwrite.py
"""prepare-send never overwrites a different sendable draft already in the output folder."""

from __future__ import annotations

from test_prepare_send import (  # noqa: F401  (fixtures)
    NOW,
    ready,
    fixed_now,
    Setup,
)

from cottonwood.cli import EXIT_OK, EXIT_REFUSED


def test_a_different_existing_sendable_is_not_overwritten(ready: Setup) -> None:
    ready.out.mkdir(parents=True)
    other = ready.out / "1-1.md"
    other.write_bytes(b"another lead's sendable\n")
    assert ready.prepare() == EXIT_REFUSED
    assert other.read_bytes() == b"another lead's sendable\n"
    assert ready.activities("draft_prepared") == []


def test_an_identical_existing_sendable_is_reused(ready: Setup) -> None:
    ready.out.mkdir(parents=True)
    (ready.out / "1-1.md").write_bytes(ready.draft.read_bytes())
    assert ready.prepare() == EXIT_OK
    assert len(ready.activities("draft_prepared")) == 1
