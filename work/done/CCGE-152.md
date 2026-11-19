# CCGE-152 — record-run: tokens and cost are optional, for subscription plans where /cost shows no dollar figure

## Goal
Cottonwood runs Claude on a subscription plan (config/pilot.yaml: no dollar cap). On 2026-11-18 the developer could not record a research run: `/cost` does not exist or shows no cost in their Claude Code, and `cottonwood record-run` requires --tokens, --cost and --cost-source. A run record must not force made-up numbers: when the developer has no figure, the run is still recorded and its tokens and cost are stored as unknown.

## Inputs
cottonwood/runs.py (parse_tokens, parse_cost, record function ~L100-140, the summary line ~L50-57); cottonwood/cli.py (record-run argparse: --tokens, --cost, --cost-source, --estimated are required today); cottonwood/migrations/002_core.sql agent_runs (tokens, cost_usd, cost_source, cost_estimated are already nullable); cottonwood/report.py _run_costs (~L406: already skips a NULL cost_usd); docs/runbook.md 'Research run' steps 5-7 and the prepare-outreach run steps (~L207-220); .claude/skills/research-prospects/SKILL.md and .claude/skills/prepare-outreach/SKILL.md 'After the run' steps. Tests: tests/test_record_run.py, tests/test_record_run_tokens_limit.py, tests/test_record_run_ended_future.py, tests/test_report_costs.py, tests/test_research_skill.py (checks the after-run text names /cost and --cost-source claude-code-cost).

## Constraints
No schema migration (the columns are already nullable). When a value is given, the existing validation is unchanged (whole-number tokens, plain-decimal cost, a known cost source). --cost-source and --estimated describe a cost, so they are refused without --cost; --cost without --cost-source is refused as today. Never store 0 in place of an unknown. Keep the existing after-run text in both skills (an existing test checks it names /cost and --cost-source claude-code-cost); only add a sentence. Synthetic test fixtures only. Decided 2026-11-18 (developer): the flag-dependency refusals exit EXIT_USAGE (2) with a message naming the flag (e.g. 'error: --cost-source needs --cost'), checked before the database is opened. prepare-outreach/SKILL.md has no 'After the run' section, so for prepare-outreach the sentence goes only in the runbook's Drafting run steps; that skill file is not edited.

## Plan
1. cli.py: make --tokens, --cost and --cost-source optional for record-run.
2. runs.py: tokens and cost may be None; store NULL for each missing value (cost_source and cost_estimated NULL too when there is no cost); refuse --cost-source or --estimated without --cost, and --cost without --cost-source, with a usage error (exit 2) naming the flag, before db.connect.
3. runs.py: the printed summary says 'tokens not recorded' and/or 'cost not recorded' instead of a number when missing.
4. Check that report.py counts a run with no cost in neither the observed nor the estimated total; adjust only if it does not.
5. docs/runbook.md (Research run and Drafting run steps) and the research-prospects skill's after-run steps: add that on a subscription plan with no cost figure, --tokens and --cost (and --cost-source) are left out.
6. Add pytest cases for the ACs; run all checks.

## Acceptance Criteria
- [x] A pytest test runs `record-run` with every required flag but no --tokens, --cost, --cost-source or --estimated, asserts exit 0, and asserts the stored agent_runs row has NULL tokens, cost_usd, cost_source and cost_estimated.
- [x] A pytest test runs `record-run` with --tokens 127190 and no cost flags, asserts exit 0 and the stored tokens is 127190 with cost_usd NULL; the printed summary contains 'cost not recorded'.
- [x] A pytest test asserts `record-run` exits with a usage error naming the flag for each of: --cost-source without --cost, --estimated without --cost, and --cost without --cost-source; and that it writes no agent_runs row in each case.
- [x] A pytest test asserts `cottonwood report` over a period with one run that has no cost and one run with cost 2.50 (observed) shows the observed model cost as 2.50 and the estimated model cost as 0.
- [x] docs/runbook.md and the 'After the run' section of .claude/skills/research-prospects/SKILL.md each say that --tokens and --cost may be left out when no figure is available; `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-18.

## Depends on
_None._
