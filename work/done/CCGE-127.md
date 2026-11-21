# CCGE-127 — Tests for the database-error paths of approve, claims and suppress

## Goal
Pin that a sqlite3.Error during approve, claims or suppress prints one 'error: could not ...' line and exits 1 instead of a traceback.

## Inputs
cottonwood/cli.py _run_approve, _run_claims, _run_suppress,review finding F-testing-3 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] With gate.approve, claims.effective_statuses and gate.suppress each monkeypatched to raise sqlite3.OperationalError, the matching command exits 1 and prints one stderr line starting 'error: could not'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
