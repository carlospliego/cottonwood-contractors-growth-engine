# CCGE-093 — CSV research rows with more cells than the header lose the extra cells silently

## Goal
A CSV row with more cells than header columns is rejected instead of importing truncated values.

## Inputs
cottonwood/validate.py:213-218 (csv.DictReader None key dropped),review 20261115-164502 finding F-correctness-3

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A CSV whose second data row has one cell more than the header produces a rejection for that record (record 2) naming the row, and imports no lead for it, while a well-formed first row still imports.
- [ ] A CSV whose rows all match the header imports as before (existing CSV import tests pass unchanged).
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
