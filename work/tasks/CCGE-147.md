# CCGE-147 — Deletion requests remove personal details from activity records (founder decision: Option A)

## Goal
Resolve the R-35/R-17 conflict as decided in the 2026-11-15 founder brief: for a deletion request only, personal details are removed from that contact's activity records, the removal is itself logged without personal data, and the suppression entry is kept. Plan with /sir:plan before building (it changes the spec and an append-only rule).

## Inputs
docs/cottonwood-growth-engine.md R-17 and R-35,docs/runbook.md Deletion requests,cottonwood/db.py,cottonwood/events.py,cottonwood/gate.py

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] docs/cottonwood-growth-engine.md R-17 states that a deletion request is the one exception under which activity records are changed, and R-35 says the procedure removes the person's details from activity records.
- [ ] A test in tests/ shows that after the deletion-request command runs for a contact with a name, email, phone and a note in two activity payloads, no row in contacts or activities contains any of those four values, a new activity records the removal with no personal data in its payload, and the contact's suppression entry is unchanged.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
