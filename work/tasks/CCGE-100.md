# CCGE-100 — Test evidence dedupe key parts and CSV re-import

## Goal
Tests fail if any part of the evidence dedupe key is dropped, or if a CSV re-import does not match.

## Inputs
cottonwood/prospects.py:284-307 (_evidence_key, _insert_new_evidence),review 20261115-164502 finding F-testing-3

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] For each of url, observed_at, excerpt and observation, a test re-imports a matched record whose only change is that one part of one evidence item and asserts exactly one new evidence row.
- [ ] A record with two identical evidence items imports one evidence row.
- [ ] Importing the same CSV file twice prints 'imported 0, matched N, rejected 0' on the second run, with N the number of rows, and leaves every table's row count unchanged.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
