# CCGE-044 — COUNTED_LEADS_FILTER comment says 'the report reuses this' but no report uses it

## Goal
Reword to 'a later report should reuse this' (or drop the claim) and qualify as leads.is_test.

## Inputs
cottonwood/review.py:14-16,review finding F-maintainability-3 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Reword to 'a later report should reuse this' (or drop the claim) and qualify as leads.is_test. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.
- [x] The changes to existing test `tests/test_review.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: test_counted_leads_filter_is_the_non_test_condition pins the exact string 'is_test = 0'; this task's AC requires qualifying it as leads.is_test, so the expected string becomes 'leads.is_test = 0'. No other test in the file changes).

All criteria verified 2026-11-20.

## Depends on
_None._
