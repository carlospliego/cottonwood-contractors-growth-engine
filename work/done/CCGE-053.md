# CCGE-053 — Review tests pin the clock but never assert the Generated line, the empty-database message, or anything rea...

## Goal
Assert the full empty-database output and the Generated line. Add a cell containing a backslash. Replace the constant test with a behavioral one, or remove it.

## Inputs
tests/test_review.py:118-125,review finding F-testing-8 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Assert the full empty-database output and the Generated line. Add a cell containing a backslash. Replace the constant test with a behavioral one, or remove it. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.
- [x] The changes to existing test `tests/test_review.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The task's AC asks for exactly this: the empty-database test is strengthened from a substring check to the full empty output including the Generated line, and the constant test (COUNTED_LEADS_FILTER == literal) is replaced by a behavioral one that runs the filter against a real and a test lead. A backslash-cell test and a Generated-line clock test are added. No other test in the file changes).

All criteria verified 2026-11-20.

## Depends on
_None._
