# CCGE-155 — Every insert's row id goes through _shared._rowid; record-run no longer turns a missing id into 0

## Goal
The 'insert returned no row id' check is copied into deletion.py, eligibility.py and send.py, and runs.py returns int(cursor.lastrowid or 0), so record-run would report run 0 instead of failing. One helper should own it.

## Inputs
cottonwood/_shared.py _rowid, cottonwood/deletion.py, cottonwood/eligibility.py, cottonwood/send.py, cottonwood/runs.py; follow-up from CCGE-075

## Constraints
No behaviour change except runs.py raising instead of returning 0.

## Plan
1. Replace each inline lastrowid check with _shared._rowid(cursor).
2. Make runs.py use it too.
3. Test that a cursor whose lastrowid is None makes the record-run insert raise sqlite3.DatabaseError.

## Acceptance Criteria
- [x] In cottonwood/, the text `lastrowid` appears only in _shared.py.
- [x] A test in tests/ shows that when the agent_runs insert's cursor has lastrowid None, recording a run raises sqlite3.DatabaseError rather than returning 0, and uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-24.

## Depends on
_None._
