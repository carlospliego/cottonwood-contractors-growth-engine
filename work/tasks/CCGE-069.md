# CCGE-069 — Explain the None sentinels on log-time/log-cost options

## Goal
Document why --estimated and --person default to None (so _void_entry_conflict can tell 'not given' from a value) (review 20261115-091006 F-maintainability-3).

## Inputs
cottonwood/cli.py:407-411 (F-maintainability-3)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] cottonwood/cli.py has a comment at the --estimated and --person arguments stating that None means the option was not given and that the --voids conflict check relies on it.

## Depends on
_None._
