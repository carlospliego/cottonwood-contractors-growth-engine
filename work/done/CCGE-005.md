# CCGE-005 — Report already-committed migrations when a later one fails

## Goal
When migration N fails after earlier ones committed, the CLI says which version the database is now at.

## Inputs
cottonwood/cli.py:_run_migrate, cottonwood/db.py:migrate (review finding F-correctness-8, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] With migrations 001 (valid) and 002 (invalid SQL) on a new database, `cottonwood migrate` exits 1 and stderr contains both the failing file name and `version 1`; a test asserts it.

All criteria verified 2026-11-21.

## Depends on
_None._
