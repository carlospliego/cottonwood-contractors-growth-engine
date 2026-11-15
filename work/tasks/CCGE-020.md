# CCGE-020 — One DatabaseMissingError shared by db and backup

## Goal
db and backup raise the same missing-database exception type (or clearly distinct names), so callers can catch it in one place.

## Inputs
cottonwood/backup.py:25-30,cottonwood/db.py (DatabaseMissingError),review finding F-maintainability-2 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] `grep -n 'class DatabaseMissingError' cottonwood/` finds exactly one definition, and existing backup and connect tests still pass.

## Depends on
_None._
