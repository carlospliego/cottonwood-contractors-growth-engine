# CCGE-071 — Make void_entry follow the other log functions' conventions

## Goal
Compute the current time inside void_entry and validate its actor the way the other log functions do (review 20261115-091006 F-maintainability-5).

## Inputs
cottonwood/events.py:622-657 void_entry (F-maintainability-5)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] void_entry no longer takes a now argument and reads timeutil.utc_now() itself, and its callers and tests pass without passing a time.
- [x] The changes to existing test `tests/test_events_void_definition.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: void_entry no longer takes a now argument (the AC); its two calls drop the NOW argument, and the file's fixed_now fixture already pins timeutil.utc_now).

All criteria verified 2026-11-20.

## Depends on
_None._
