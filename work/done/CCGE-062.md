# CCGE-062 — Cover correction refusals for bad and future --at, blank --actor, --procurement-url and bad databases (F-testing-1)

## Goal
Test validate_correction's own checks and the log-event correction CLI refusals (review 20261115-091006 F-testing-1). A ready test exists at .sir/runs/fix/20261115-091006/F-testing-1.regression; it failed sir's red step only because of the import problem filed alongside.

## Inputs
cottonwood/events.py:344-352 validate_correction (review 20261115-091006 F-testing-1),cottonwood/cli.py _run_correction

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Tests assert that log-event 1 correction exits 1 and writes nothing for an unparseable --at, a future --at, a blank --actor, a --procurement-url, a missing database and an unmigrated database, and the future --at test fails when the `if occurred_at > now` check in validate_correction is removed.

All criteria verified 2026-11-20.

## Depends on
_None._
