# Research Skill — implementation plan

<!-- Written by /sir:plan. The HOW for spec.md. -->

## Approach
Four small pieces, no new dependency and no migration (`agent_runs` exists since 002):
1. `record-run` in a new `cottonwood/runs.py` (architecture: "runs.py — record-run for Claude skill runs"): parse and check every field, refuse naming the field, else insert one `agent_runs` row in its own transaction. The report already sums `agent_runs.cost_usd` by `started_at` and `cost_estimated`, so no report change.
2. `prospects-import --check`: reuse `validate.load_records` and `validate.validate_record` with the same checklist keys; print each `Rejection.line()` on stderr and a `check:` summary; never open a write transaction (the database is not even needed).
3. `.claude/skills/research-prospects/SKILL.md`: frontmatter (`name`, `description`, `version: 1.0.0`, `allowed-tools: WebSearch, WebFetch, Read, Write, Glob, Grep`), inputs, procedure, hard rules, output path and schema, one worked example, and the after-run steps. Tests parse the frontmatter, check the rules, and run the worked example through `--check` and a real import.
4. `tests/test_no_send_credentials.py` with a small matcher over `git ls-files`, and a `## Research run` section in `docs/runbook.md`.

## Components & changes
- `cottonwood/runs.py` (new): `RunError(field, message)`, `RunRecord` dataclass, `VALIDATIONS = ("passed", "failed")`, `COST_SOURCES = ("claude-code-cost", "billing-console")`, `parse_cost` (plain decimal regex, ≥ 0, ≤ 4 places), `parse_tokens`, `record_run(conn, record) -> int`, and `RunRecord.line(run_id)`.
- `cottonwood/cli.py`: `record-run` Command (`--skill`, `--skill-version`, `--model`, `--started`, `--ended`, `--input`, `--output`, `--validation` choices, `--tokens`, `--cost`, `--cost-source` choices, `--estimated`, `--db`); `prospects-import` gains `--check`.
- `.claude/skills/research-prospects/SKILL.md` (new).
- `docs/runbook.md`: `## Research run` section.
- Tests: `tests/test_record_run.py`, `tests/test_prospects_check.py`, `tests/test_research_skill.py`, `tests/test_no_send_credentials.py`, `tests/test_runbook_research.py`.

## Data & interfaces
- `agent_runs` columns written: skill, skill_version, model, started_at, ended_at (UTC `...Z` via `timeutil.parse_received`), input_ref, output_ref, validation, tokens, cost_usd (the cost text as given, e.g. `3.25`), cost_source, cost_estimated (0/1).
- `record-run` stdout: `run N recorded: SKILL VERSION, COST USD (SOURCE)` or `(SOURCE, estimated)`. Refusals: `error: FIELD: MESSAGE`, exit 1. Usage errors (choices) exit 2.
- `prospects-import FILE --check` stdout: `check: N valid, M rejected`; stderr: one `rejected record N (ID): FIELD: RULE` per rejection; exit 0 when none rejected, else 1.
- Skill output: `out/research/YYYY-MM-DD-SLUG.json`, a JSON array of research records per `cottonwood/schemas/research-record.schema.json`.

## Risks & rollback
- A skill that drifts from the schema produces files that fail import: caught by the worked-example test and, at run time, by `--check` before import (R-25, never repaired by guessing).
- Prompt injection through web text: the skill is told text is data only, and it has no Bash, no database and no CLI, so the worst output is an invalid or wrong file that the founder's hand review (Gate 1) rejects (R-27, architecture decision 6).
- The credential scan could flag the `.env.example` comments: its matcher requires an assignment with a non-empty value, and a unit test pins that the template is not flagged.
- Rollback: revert the PR; `record-run` rows are plain inserts, and a wrong one is left in place and noted (agent_runs has no void mechanism; out of scope).

## Test strategy
- `record-run`: CLI tests with `timeutil.utc_now` pinned to 2026-12-01T00:00:00Z: the stored row field by field, the printed line, every refusal (blank fields, bad times, ended before started, future start, tokens, cost forms), argparse choices exit 2, and the report's `Model cost`/`Model cost estimated` lines for observed and estimated runs.
- `--check`: one valid + one invalid record, all valid, unreadable file, checklist keys honored, and row counts of every table unchanged.
- Skill: frontmatter parsed with PyYAML, tools allowlist, version form, the rule sentences present, the paths named, and the worked example through `--check` and import into a fresh database.
- Credentials: matcher unit tests plus the whole-repo scan.

## Sequencing
T-01 (`record-run`) and T-02 (`--check`) are independent; T-03 (skill) depends on T-02, since its example test and after-run steps use `--check`, and on T-01, since the steps name `record-run`; T-04 (credential guard and runbook) depends on T-01 and T-02 for the commands it documents.
