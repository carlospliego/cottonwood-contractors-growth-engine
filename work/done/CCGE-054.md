# CCGE-054 — The runbook's inbound commands and expected outputs are checked only as substrings, never run

## Goal
Extract the indented log-inbound commands and the SQL block from the runbook, run them against a temp database through main() and sqlite3, and assert the review output the runbook describes.

## Inputs
tests/test_runbook_inbound.py:72-77,review finding F-testing-9 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Extract the indented log-inbound commands and the SQL block from the runbook, run them against a temp database through main() and sqlite3, and assert the review output the runbook describes. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
