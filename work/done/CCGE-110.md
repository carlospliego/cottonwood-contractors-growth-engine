# CCGE-110 — record-run command: Claude skill runs with version, model, times, files, validation and cost source

## Goal
Record every Claude skill run in agent_runs with its version, model, start and end time, input and output references, validation result, tokens and cost from a named source, so the report's model-cost lines include it (R-26).

## Inputs
Spec: `work/specs/research-skill/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-4.3)
Plan: `work/specs/research-skill/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/runs.py: RunError(field, message) with str 'FIELD: MESSAGE'; VALIDATIONS ('passed','failed'); COST_SOURCES ('claude-code-cost','billing-console'); RunRecord frozen dataclass with line(run_id) -> 'run N recorded: SKILL VERSION, COST USD (SOURCE)' or '(SOURCE, estimated)'; build_record(...) checks non-blank skill/skill_version/model/input/output, parses started/ended with timeutil.parse_received (ValueError -> RunError), refuses ended < started and started > now, tokens a non-negative whole number (regex ^[0-9]+$), cost a plain non-negative decimal with at most 4 places (regex, no exponent, no sign); record_run(conn, record) inserts in one BEGIN IMMEDIATE transaction and returns the id.
2. cottonwood/cli.py: record-run Command with --skill, --skill-version, --model, --started, --ended, --input, --output (all required), --validation choices, --tokens, --cost, --cost-source choices (required), --estimated store_true, --db; refusals print 'error: FIELD: MESSAGE' and exit 1.
3. tests/test_record_run.py with utc_now pinned to 2026-12-01T00:00:00Z: stored row, printed line, estimated flag, billing-console, every refusal, argparse exit 2, and report lines for observed and estimated runs.

## Acceptance Criteria
- [x] 'cottonwood record-run --skill research-prospects --skill-version 1.0.0 --model claude-opus-5-5 --started "2026-11-30 09:00" --ended "2026-11-30 09:40" --input "brief: GC firms in Salt Lake County" --output out/research/2026-11-30-gc.json --validation passed --tokens 120000 --cost 3.25 --cost-source claude-code-cost' exits 0, prints 'run 1 recorded: research-prospects 1.0.0, 3.25 USD (claude-code-cost)', and stores one agent_runs row with skill research-prospects, skill_version 1.0.0, model claude-opus-5-5, started_at 2026-11-30T16:00:00Z, ended_at 2026-11-30T16:40:00Z, input_ref 'brief: GC firms in Salt Lake County', output_ref out/research/2026-11-30-gc.json, validation passed, tokens 120000, cost_usd '3.25', cost_source claude-code-cost and cost_estimated 0.
- [x] With --estimated the row has cost_estimated 1 and the printed line ends '(claude-code-cost, estimated)'; --cost-source billing-console is accepted and stored; after recording an observed run of 3.25 and an estimated run of 1.1 both started 2026-11-30, 'cottonwood report --from 2026-11-30 --to 2026-11-30' output contains '- Model cost: 4.35', '- Model cost observed: 3.25' and '- Model cost estimated: 1.10'.
- [x] Each of these exits 1 with a stderr line starting 'error: FIELD:' that names the offending option's field and writes no agent_runs row: --skill '  '; --skill-version '  '; --model '  '; --input '  '; --output '  '; --started 'yesterday'; --ended '2026-11-30 25:00'; --ended earlier than --started; --started later than now (2026-12-01 00:00 Denver with utc_now pinned to 2026-12-01T00:00:00Z); --tokens -1; --tokens 1.5; --cost -1; --cost 1e3; --cost 1.23456.
- [x] '--validation maybe' and '--cost-source guess' are refused by argparse with exit 2 and write no row.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
