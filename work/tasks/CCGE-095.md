# CCGE-095 — prospects-import uses a deferred BEGIN, so a concurrent writer aborts the import

## Goal
The import takes the write lock up front (BEGIN IMMEDIATE) so the busy timeout is honoured and matching and writing are serialized.

## Inputs
cottonwood/prospects.py:121 (conn.execute("BEGIN")),cottonwood/db.py:135 (migrations use BEGIN IMMEDIATE),review 20261115-164502 finding F-correctness-6

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] cottonwood/prospects.py import_records begins its transaction with BEGIN IMMEDIATE.
- [ ] A test holds a write lock on the database from a second connection and releases it after 0.2 seconds; prospects-import started meanwhile with the default busy timeout completes with exit 0 and imports its record.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
