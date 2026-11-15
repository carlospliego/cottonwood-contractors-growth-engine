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
- [ ] cottonwood/events.py defines CORRECTION_KIND and STAGE_CHANGE_KIND and contains no other Python string literal 'correction' or 'stage_change' outside those definitions and the SQL built from them.

## Depends on
_None._
