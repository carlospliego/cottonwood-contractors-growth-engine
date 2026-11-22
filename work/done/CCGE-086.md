# CCGE-086 — Test that non-finite agent_runs.cost_usd values are skipped

## Goal
Cover the is_finite guard in the report's agent-run cost reading so removing it fails a test.

## Inputs
cottonwood/report.py:410-411 (_run_costs),tests/test_report_costs.py,review finding F-testing-2 (run 20261115-161134)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test seeds in-period agent_runs rows with cost_usd 'NaN' and 'Infinity' plus one of 1.00 and asserts the report's model cost is 1.00 and the command exits 0.
- [x] Deleting the is_finite check in _run_costs makes that test fail.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
