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
- [ ] void_entry no longer takes a now argument and reads timeutil.utc_now() itself, and its callers and tests pass without passing a time.

## Depends on
_None._
