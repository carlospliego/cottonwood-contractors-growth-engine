# CCGE-114 — prospects-import --check: account for leads an earlier record in the same file would create

## Goal
Make --check agree with the import when a later record in a file would match a lead, organization or contact that an earlier record of the same file creates, so the check never reports a different outcome than the import.

## Inputs
cottonwood/prospects.py:148-165 (check_records),cottonwood/prospects.py import_records (later records see earlier ones as stored),review finding F-correctness-2 (run code/20261115-180811)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] For a file whose records 1 and 2 describe the same organization and lead, 'prospects-import FILE --check' prints the same rejection lines and the same valid/rejected counts as the rejected lines and the 'rejected' count of 'prospects-import FILE' on a fresh database.
- [x] --check still writes nothing: the row counts of organizations, contacts, leads, evidence and activities are unchanged after it.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
