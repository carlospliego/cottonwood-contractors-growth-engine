# CCGE-107 — Rename _import_review_config to _load_review_config (used by review too)

## Goal
The helper that loads the review checklists is named for prospects-import, but the review command also calls it; rename it so a change to its fallback is not mistaken for an import-only change.

## Inputs
cottonwood/cli.py:688-698 (_import_review_config),cottonwood/cli.py:248 (_run_review caller),review finding F-maintainability-1 (run code/20261115-173820)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] grep -n '_import_review_config' cottonwood/ tests/ returns no matches and cottonwood/cli.py defines _load_review_config, called by both _run_review and the prospects-import handler.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
