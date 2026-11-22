# CCGE-099 — Test every compared field in re-import difference reporting

## Goal
Each field compared on re-import has a test that fails if the wrong column or comparison is used.

## Inputs
cottonwood/prospects.py:356-382 (_differences pairs),tests/test_prospects_reimport.py:304-323,review 20261115-164502 finding F-testing-2

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A parametrized test in a new test file changes, one at a time, organization.name, organization.domain-free name match case, organization.type, contact.name, contact.phone, contact.source_url, next_action, value.amount, value.basis and referred_by on a matched record, and asserts a 'FIELD differs' line naming exactly that field with the stored and incoming values.
- [x] A test re-imports a record with a contact against a matched lead that has no stored contact and asserts the printed outcome.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
