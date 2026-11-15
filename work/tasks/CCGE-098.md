# CCGE-098 — Lead type and initial stage literals are defined separately in validate, report, events and prospects

## Goal
The lead type names and the 'researched' stage are each defined once and imported where used.

## Inputs
cottonwood/validate.py:28-29,cottonwood/report.py:84-85,cottonwood/events.py:36-56,cottonwood/prospects.py:28,review 20261115-164502 finding F-maintainability-2

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] grep -rn '"direct_candidate"' cottonwood/*.py returns exactly one line, a constant definition.
- [ ] grep -rn '"relationship_prospect"' cottonwood/*.py returns exactly one line, a constant definition.
- [ ] prospects.py takes its imported stage from the same constant events.py uses for 'researched' (grep '"researched"' cottonwood/prospects.py finds nothing).
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
