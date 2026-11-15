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
- [ ] Reword to 'a later report should reuse this' (or drop the claim) and qualify as leads.is_test. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
