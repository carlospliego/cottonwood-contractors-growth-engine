# CCGE-143 — Runbook: a drafting run from export to logged send

## Goal
Document the drafting run so every draft is exported, recorded and gated the same way (R-20, R-21, R-26).

## Inputs
Spec: `work/specs/outreach-skill/spec.md` (AC-3.1, AC-4.1)
Plan: `work/specs/outreach-skill/plan.md`

## Constraints
_None._

## Plan
1. docs/runbook.md: '## Drafting run' after '## Research run': export to out/leads/ID.json; run prepare-outreach; note times; record-run --skill prepare-outreach with cost source; founder reads the brief and draft; approve draft; prepare-send; founder sends from their own client; log-outreach with --prepared.
2. tests/test_runbook_drafting.py; tests/test_runbook_inbound.py heading list gains 'Drafting run'.

## Acceptance Criteria
- [x] docs/runbook.md's level-2 headings are, in order, Restore from backup, Re-applying suppression after a restore, Deletion requests, Inbound verification checklist, Relay, Research run and Drafting run, and the Drafting run section contains 'cottonwood review --lead', 'prepare-outreach', 'cottonwood record-run --skill prepare-outreach', 'cottonwood approve draft', 'cottonwood prepare-send' and 'cottonwood log-outreach'; a test in tests/ asserts each.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-142

## Tests to change
- `tests/test_runbook_inbound.py`
