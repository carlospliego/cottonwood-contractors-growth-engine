# CCGE-126 — events: expose public helpers instead of underscore names used by gate, claims and cli

## Goal
Give the events helpers that other modules use (_insert_activity, _day_start, _voided_sql, _parse_entry_date) public names (aliases are fine), and switch gate.py, claims.py and cli.py to them, so their contract is explicit.

## Inputs
cottonwood/events.py,cottonwood/gate.py:198-206,cottonwood/claims.py,cottonwood/cli.py _run_approve,review finding F-maintainability-2 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] 'grep -nE "events\._[a-z]" cottonwood/gate.py cottonwood/claims.py' finds no match, and cli.py's approve handler calls no events._ name.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
