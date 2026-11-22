# CCGE-006 — Tie usage-error exits to EXIT_USAGE and drop the unreachable string branch

## Goal
The CLI's exit-code mapping uses its own constants and has no dead branches.

## Inputs
cottonwood/cli.py:_exit_code and EXIT_USAGE (review findings F-maintainability-1 and F-maintainability-2, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] `grep -n EXIT_USAGE cottonwood/cli.py` shows it used in _exit_code, and `main([])` still returns 2 in tests.
- [x] _exit_code has no branch that maps a string SystemExit code to EXIT_REFUSED, and `uv run mypy` and `uv run pytest` pass.

All criteria verified 2026-11-21.

## Depends on
_None._
