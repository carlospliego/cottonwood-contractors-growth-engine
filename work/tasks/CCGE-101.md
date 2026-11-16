# CCGE-101 — record_id is unbounded and unfiltered, yet stored in append-only activities and echoed to the terminal

## Goal
record_id is a short identifier without control characters, and values echoed in outcome and difference lines cannot carry terminal escapes.

## Inputs
cottonwood/validate.py:326-331 (_record_id),cottonwood/prospects.py payload record_id and difference_lines,review 20261115-164502 finding F-security-basics-2

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A record whose record_id is 65 characters long, or contains '@' or a control character, is rejected with 'record_id' as the field, and its import_rejected payload does not contain that value.
- [ ] A record_id 'acme-1.v2_x' still imports and is printed as '(acme-1.v2_x)'.
- [ ] A re-import where the incoming organization.category contains an ESC character (\u001b) prints the difference line without that character.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
