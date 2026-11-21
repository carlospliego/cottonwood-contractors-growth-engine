# CCGE-084 — Report handles malformed stored payloads and timestamps without a traceback

## Goal
One bad stored row (non-object JSON payload, invalid JSON, or an unparseable timestamp) must not crash the whole weekly report with a Python traceback.

## Inputs
cottonwood/report.py:228-233 (_qualified),cottonwood/report.py:204, 412 (local_date calls),cottonwood/cli.py _run_report,review finding F-correctness-2 (run 20261115-161134)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A counted stage_change activity in the period with payload '[]' leaves `cottonwood report --period 7d` exiting 0 or exiting 1 with stderr starting 'error:'; stderr never contains 'Traceback'.
- [x] An agent_runs row with started_at 'not-a-time' leaves `cottonwood report --period 7d` exiting 0 or exiting 1 with stderr starting 'error:'; stderr never contains 'Traceback'.
- [x] _qualified reads payloads through the same dict guard as _payload: grep of cottonwood/report.py finds no `json.loads(` call outside _payload.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
