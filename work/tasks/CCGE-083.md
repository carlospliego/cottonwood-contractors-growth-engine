# CCGE-083 — Report survives very large cap and cost values instead of an InvalidOperation traceback

## Goal
A model-cost cap or agent-run cost too large for 0.01 quantization in the default Decimal context must not end `cottonwood report` in a traceback.

## Inputs
cottonwood/report.py:531-533 (money),cottonwood/config.py:82-98 (_cost_cap),review finding F-correctness-1 (run 20261115-161134)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] With config report.model_cost_cap_usd set to the string "1000000000000000000000000000000", `cottonwood report --period 7d` either exits 0 printing the cap or exits 1 with stderr starting 'error:' naming report.model_cost_cap_usd; stderr never contains 'Traceback'.
- [ ] With an agent_runs row in the period whose cost_usd is '1E+30', `cottonwood report --period 7d` exits 0 or 1 with stderr starting 'error:', and stderr never contains 'Traceback'.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
