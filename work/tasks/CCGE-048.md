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
- [ ] Derive the expected version from len(db.discover_migrations()) or a shared LATEST_VERSION test constant. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
