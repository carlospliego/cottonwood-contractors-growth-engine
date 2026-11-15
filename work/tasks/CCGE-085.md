# CCGE-085 — Make the events and review helpers the report uses public

## Goal
report.py should depend only on public names in events and review, so changes to those modules' private helpers cannot silently break the report.

## Inputs
cottonwood/report.py:252, 567, 612,cottonwood/events.py:725 (_entries_in_range),cottonwood/review.py:84 (_cell),review finding F-maintainability-1 (run 20261115-161134)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] grep of cottonwood/report.py finds no `events._` and no `review._` references.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
