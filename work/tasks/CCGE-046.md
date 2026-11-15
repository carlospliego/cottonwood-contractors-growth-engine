# CCGE-046 — inbound_counts total counts rows that the per-channel/segment breakdown silently drops

## Goal
Count unknown values in an 'other' bucket or document that the breakdown may not sum to total.

## Inputs
cottonwood/review.py:63-81,review finding F-maintainability-5 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Count unknown values in an 'other' bucket or document that the breakdown may not sum to total. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
