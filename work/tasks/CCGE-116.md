# CCGE-116 — Test prospects-import --check with a valid stored referrer

## Goal
Pin check/import parity for referred_by: a record whose referrer is a stored relationship-prospect lead passes --check and imports.

## Inputs
cottonwood/prospects.py:148-165 (check_records, _referrer_rejection),tests/test_prospects_check.py,review finding F-testing-1 (run code/20261115-180811)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test stores a relationship_prospect lead with id N, writes a direct_candidate record with referred_by N, and asserts 'prospects-import FILE --check' exits 0 with 'check: 1 valid, 0 rejected' and the import then creates the lead with referred_by N.
- [ ] The same test with referred_by naming a stored direct_candidate lead asserts --check exits 1 with a 'referred_by' rejection line identical to the import's.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
