# CCGE-045 — 'inbound_inquiry' type literal repeated across five SQL strings in two modules

## Goal
Add LEAD_TYPE = 'inbound_inquiry' in inbound.py and bind it as a parameter in all queries.

## Inputs
cottonwood/review.py:58-79,review finding F-maintainability-4 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Add LEAD_TYPE = 'inbound_inquiry' in inbound.py and bind it as a parameter in all queries. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
