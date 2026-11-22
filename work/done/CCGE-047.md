# CCGE-047 — --db option and default-path resolution copy-pasted into every command

## Goal
Add a _add_db_argument(parser) helper and a _db_path(args) helper used by all commands.

## Inputs
cottonwood/cli.py:133-138,review finding F-maintainability-6 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Add a _add_db_argument(parser) helper and a _db_path(args) helper used by all commands. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
