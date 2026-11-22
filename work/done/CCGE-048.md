# CCGE-048 — Tests hard-code the latest schema version in 16 places across 5 files

## Goal
Derive the expected version from len(db.discover_migrations()) or a shared LATEST_VERSION test constant.

## Inputs
tests/test_migrate.py:59-61,review finding F-maintainability-7 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Derive the expected version from len(db.discover_migrations()) or a shared LATEST_VERSION test constant. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.
- [x] The changes to existing test `tests/test_migrate.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).
- [x] The changes to existing test `tests/test_schema.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).
- [x] The changes to existing test `tests/test_backup.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).
- [x] The changes to existing test `tests/test_inbound.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).
- [x] The changes to existing test `tests/test_prospects_checklist.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).
- [x] The changes to existing test `tests/test_runbook_restore.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The test hard-codes the latest schema version (6); this task derives it as LATEST_VERSION = len(db.discover_migrations()). Only those literals change: every assertion keeps checking the same value today, and nothing else in the file changes).

All criteria verified 2026-11-20.

## Depends on
_None._
