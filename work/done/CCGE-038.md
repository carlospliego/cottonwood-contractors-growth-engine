# CCGE-038 — log-inbound and review open a database without checking it is migrated, so an un-migrated file fails with a...

## Goal
After connect, compare db.user_version(conn) with the newest discovered migration and refuse with 'database at version N, run `cottonwood migrate`' when it is lower.

## Inputs
cottonwood/cli.py:176-196,review finding F-correctness-6 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] After connect, compare db.user_version(conn) with the newest discovered migration and refuse with 'database at version N, run `cottonwood migrate`' when it is lower. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
