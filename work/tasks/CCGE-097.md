# CCGE-097 — Remove unused RULE_REQUIRED, DIRECT and ProspectRecord.label from validate.py

## Goal
validate.py holds no constants or methods that nothing uses, so editing one cannot be mistaken for changing behaviour.

## Inputs
cottonwood/validate.py:28-41, 171-173,review 20261115-164502 finding F-maintainability-1

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] grep -wn RULE_REQUIRED cottonwood/ finds either no match or a use outside its definition line.
- [ ] grep -n 'def label' cottonwood/validate.py finds no label method on ProspectRecord, or the method has a caller in cottonwood/.
- [ ] Rejection output for a missing required field still reads 'FIELD: required' (tests/test_prospects_import.py passes unchanged).
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
