# CCGE-070 — Refuse or document a blank --stage on log-event

## Goal
Stop a blank --stage from silently meaning 'no move' while the comment says blank text stays blank (review 20261115-091006 F-maintainability-4).

## Inputs
cottonwood/events.py:142-146 validate_event (F-maintainability-4)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] log-event with --stage ' ' either exits 1 and writes nothing, asserted by a test, or the comment in validate_event states that a blank stage means no move.

All criteria verified 2026-11-20.

## Depends on
_None._
