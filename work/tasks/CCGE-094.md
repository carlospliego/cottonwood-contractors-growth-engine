# CCGE-094 — Research import accepts Infinity and NaN for founder_time_h

## Goal
founder_time_h must be a finite number of hours; Infinity and NaN are rejected.

## Inputs
cottonwood/validate.py:246-249 and _csv_scalar 288-293,cottonwood/schemas/research-record.schema.json:53,review 20261115-164502 finding F-correctness-4

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A JSON file whose record has founder_time_h Infinity is rejected with field founder_time_h, and no lead is written.
- [ ] A JSON record with founder_time_h NaN and a CSV row with founder_time_h 'inf' are each rejected with field founder_time_h.
- [ ] A record with founder_time_h 1.5 imports with leads.founder_time_h 1.5.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
