# CCGE-065 — Refuse a reverting correction dated before the lead's latest stage change

## Goal
Keep stage history ordered by occurred_at consistent with leads.stage when a correction reverts a stage (review 20261115-091006 F-correctness-4).

## Inputs
cottonwood/events.py:390-409 log_correction (F-correctness-4)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A correction that would revert a stage, with --at earlier than the lead's latest effective stage change including reverts, exits 1 and writes nothing, asserted by a test.

## Depends on
_None._
