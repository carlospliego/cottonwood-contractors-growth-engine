# CCGE-037 — The same-day duplicate check and the insert are not in one transaction

## Goal
Run `BEGIN IMMEDIATE` before the duplicate check, and re-check under the lock before inserting (the prompt can stay outside if the check is repeated).

## Inputs
cottonwood/cli.py:186-192,review finding F-correctness-5 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Run `BEGIN IMMEDIATE` before the duplicate check, and re-check under the lock before inserting (the prompt can stay outside if the check is repeated). A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
