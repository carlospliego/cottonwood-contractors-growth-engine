# CCGE-072 — Name the correction and stage_change activity types as constants

## Goal
Replace the bare 'correction' and 'stage_change' literals in events.py with named constants, as the time and cost kinds already are (review 20261115-091006 F-maintainability-6).

## Inputs
cottonwood/events.py:419-423 and the SQL fragments (F-maintainability-6)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] cottonwood/events.py defines CORRECTION_KIND and STAGE_CHANGE_KIND and contains no other Python string literal 'correction' or 'stage_change' outside those definitions and the SQL built from them.
- [x] The changes to existing test `tests/test_events_void_definition.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the void predicate's source text is now built from CORRECTION_KIND (the AC forbids the bare 'correction' literal), so the single-definition check counts "c.type = '{CORRECTION_KIND}'" instead of "c.type = 'correction'"; it still asserts the predicate is written exactly once).

All criteria verified 2026-11-20.

## Depends on
_None._
