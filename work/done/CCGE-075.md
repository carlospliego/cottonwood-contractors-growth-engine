# CCGE-075 — Share _clean and _rowid between inbound.py and events.py

## Goal
Remove the verbatim copies of the _clean and _rowid helpers (review 20261115-091006 F-maintainability-9).

## Inputs
cottonwood/events.py:117-169 and cottonwood/inbound.py (F-maintainability-9)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] _clean and _rowid are each defined once in the cottonwood package and imported where used, and the existing tests pass.

All criteria verified 2026-11-21.

## Depends on
_None._
