# CCGE-092 — Research import accepts value.amount and referred_by with a trailing newline or non-ASCII digits

## Goal
value.amount and referred_by accept only ASCII digits with no trailing newline, so what is stored can always be parsed as a Decimal or an int.

## Inputs
cottonwood/validate.py:75-77 (_DECIMAL / _INTEGER patterns),review 20261115-164502 finding F-correctness-2

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A JSON record with value.amount '100\n' is rejected with 'value.amount: decimal' and writes no lead.
- [x] A JSON record with value.amount '١٠٠' (Arabic-Indic digits) is rejected with 'value.amount: decimal'.
- [x] A record with value.amount '1500.50' still imports with leads.value_amount '1500.50'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
