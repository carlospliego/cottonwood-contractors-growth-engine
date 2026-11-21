# CCGE-091 — CSV research import cannot express an empty hypothesis or empty verified_facts

## Goal
A CSV research record should be able to carry an empty hypothesis or no verified facts, as a JSON record can, instead of being rejected as 'required'.

## Inputs
cottonwood/validate.py _csv_record (empty cells are absent),work/specs/prospect-import/plan.md CSV columns,found while verifying CCGE-089 AC1

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A CSV row whose hypothesis cell is empty imports with leads.hypothesis '' instead of being rejected with 'hypothesis: required', while a CSV without a hypothesis column is still a FileError.
- [x] A CSV row whose verified_facts cell is empty imports with leads.verified_facts '[]'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
