# CCGE-051 — DST edge handling in parse_received (fold=0 for repeated times, nonexistent spring-forward times) is untested

## Goal
Add cases for 2026-11-01 01:30 (expect 07:30Z) and 2026-03-08 02:30 (assert the chosen behavior, or reject it).

## Inputs
cottonwood/timeutil.py:42-47,review finding F-testing-6 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Add cases for 2026-11-01 01:30 (expect 07:30Z) and 2026-03-08 02:30 (assert the chosen behavior, or reject it). A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
