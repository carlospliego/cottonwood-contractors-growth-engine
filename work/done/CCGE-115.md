# CCGE-115 — record-run: refuse an --ended time later than now

## Goal
Refuse a run whose end time is in the future, like a future start, so agent_runs never holds a run that has not finished.

## Inputs
cottonwood/runs.py:121-124 (build_record time checks),review finding F-correctness-3 (run code/20261115-180811)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z, 'record-run ... --started "2026-11-30 09:00" --ended "2026-12-01 01:00"' exits 1 with a stderr line starting 'error: ended:' and writes no agent_runs row.
- [x] An --ended equal to now (2026-11-30 17:00 Denver) is accepted.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-17.

## Depends on
_None._
