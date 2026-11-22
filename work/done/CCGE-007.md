# CCGE-007 — Document that migration files must not contain transaction control

## Goal
Migration authors know the runner wraps each file in its own transaction.

## Inputs
cottonwood/migrations/001_baseline.sql header, cottonwood/db.py:_apply docstring (review finding F-maintainability-4, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] The header comment of cottonwood/migrations/001_baseline.sql and the _apply docstring both state that migration files must not contain BEGIN, COMMIT or ROLLBACK.

All criteria verified 2026-11-21.

## Depends on
_None._
