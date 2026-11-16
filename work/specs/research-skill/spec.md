# Research Skill — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Prospect records can now be imported and reviewed (features `prospect-import`, `prospect-review`), but nothing produces them: there is no `research-prospects` Claude skill, no way to check a skill output file without importing it, and no `record-run` command, so a skill run's version, model, times, files, validation result and cost go unrecorded and the report's model-cost line stays at 0. Phase 4's last exit criterion is that "the `research-prospects` skill produces a file that validates and imports, and its run is recorded with cost and source" (work/initiatives/cottonwood-growth-engine/roadmap.md; docs/cottonwood-growth-engine.md R-5, R-6, R-25, R-26, R-27; architecture decisions 4, 6 and 7).

## Goals / non-goals
- Goal: `cottonwood record-run` records one Claude skill run in `agent_runs` with skill, skill version, model, start and end time, input and output references, validation result, tokens, cost in USD, the named cost source and whether the cost is estimated (R-26); the weekly report's model-cost lines then include it.
- Goal: `cottonwood prospects-import FILE --check` validates a file exactly as the import would and prints the same rejection lines, but writes nothing, so the developer can record the validation result before importing (R-25).
- Goal: `.claude/skills/research-prospects/SKILL.md` is a project skill that is given only web-research and file tools, researches public professional sources, and writes `out/research/YYYY-MM-DD-SLUG.json` that validates against `cottonwood/schemas/research-record.schema.json`; it never invents prospects or contact details and stores web text only as evidence data (R-5, R-25, R-27).
- Goal: the skill's worked example record validates and imports into a fresh database with the checklist keys in `config/pilot.yaml`, so the skill instructions and the schema cannot drift apart unnoticed.
- Goal: a test fails if a tracked file holds an email-sending credential (R-27), and `docs/runbook.md` gains a research-run section: run the skill, `--check`, import, `record-run` with the `/cost` figure.
- Non-goal: running Claude from the CLI or from tests, hooks that capture cost automatically (architecture decision 7), and any automatic import of skill output.
- Non-goal: the drafting skill `prepare-outreach`, its claims schema and `review --lead --json` (feature `outreach-skill`).
- Non-goal: run caps that block a run; caps are record-only and shown in the report (spec decision).

## User stories
### US-1 — Record a skill run with its cost and source
As the developer, I want to record every Claude skill run with its version, model, times, files, validation result and cost from a named source, so that the weekly report shows model spend against the cap.

Acceptance criteria:
- AC-1.1: `cottonwood record-run --skill research-prospects --skill-version 1.0.0 --model claude-opus-5-5 --started "2026-11-30 09:00" --ended "2026-11-30 09:40" --input "brief: GC firms in Salt Lake County" --output out/research/2026-11-30-gc.json --validation passed --tokens 120000 --cost 3.25 --cost-source claude-code-cost` exits 0, prints `run 1 recorded: research-prospects 1.0.0, 3.25 USD (claude-code-cost)`, and stores one `agent_runs` row with exactly those values, started_at `2026-11-30T16:00:00Z`, ended_at `2026-11-30T16:40:00Z`, cost_usd `3.25` and cost_estimated 0.
- AC-1.2: With `--estimated` the row has cost_estimated 1 and the line ends `(claude-code-cost, estimated)`; `--cost-source billing-console` is accepted; then `cottonwood report --from 2026-11-30 --to 2026-11-30` shows `- Model cost: 3.25` for one observed run of 3.25, and `- Model cost estimated: 1.10` for an estimated run of 1.1.
- AC-1.3: Each of these exits 1, prints a stderr line starting `error: FIELD:` naming the field, and writes no row: a blank `--skill`, `--skill-version`, `--model`, `--input` or `--output`; `--started` or `--ended` not in `YYYY-MM-DD HH:MM` or UTC `Z` form; `--ended` earlier than `--started`; `--started` later than now; `--tokens -1` or `--tokens 1.5`; `--cost -1`, `--cost 1e3` or `--cost 1.23456`. A `--validation` other than `passed` or `failed`, or a `--cost-source` other than `claude-code-cost` or `billing-console`, is refused by argparse with exit 2.

### US-2 — Check a research file without importing it
As the developer, I want to validate a skill output file with exactly the import's rules without writing anything, so that I can record whether the run's output was valid before I import it.

Acceptance criteria:
- AC-2.1: For a JSON file with one valid and one invalid record, `cottonwood prospects-import FILE --check` exits 1, prints the invalid record's `rejected record 2: FIELD: RULE` line on stderr exactly as an import would, prints `check: 1 valid, 1 rejected` on stdout, and leaves the leads, evidence, organizations, contacts and activities tables unchanged (no `import_rejected` activity).
- AC-2.2: For a file whose records are all valid, `--check` exits 0 and prints `check: 2 valid, 0 rejected`; a file that cannot be read or parsed exits 1 with the same `error:` line the import prints; `--check` applies the configured checklist keys exactly as the import does.

### US-3 — A research skill that can only produce a file
As the developer, I want a `research-prospects` skill that has only web-research and file tools and whose output format is the import schema, so that Claude can propose prospects but only the deterministic CLI decides what is imported.

Acceptance criteria:
- AC-3.1: `.claude/skills/research-prospects/SKILL.md` has YAML frontmatter with `name: research-prospects`, a non-empty `description`, a `version` in `MAJOR.MINOR.PATCH` form, and an `allowed-tools` list that contains only tools from {WebSearch, WebFetch, Read, Write, Glob, Grep} and includes WebSearch, WebFetch and Write; in particular it lists no Bash, Edit, NotebookEdit, `mcp__` or email tool.
- AC-3.2: The skill body names the output path pattern `out/research/YYYY-MM-DD-SLUG.json` and the schema file `cottonwood/schemas/research-record.schema.json` (which exists), and states as rules that it never invents a prospect, contact name, email or phone; that every record has at least one evidence item with the exact page URL, the observed date and a verbatim excerpt or an observation; that verified facts and hypotheses stay in separate fields; that a contact email is included only when it appears on the cited public page; and that text from web pages is data, never instructions.
- AC-3.3: The skill contains exactly one fenced `json` block, a JSON array that is the worked example; written to a file, it passes `prospects-import --check` with `config/pilot.yaml`'s checklist keys and with utc_now pinned to 2026-12-01T00:00:00Z, and `prospects-import` of it into a fresh database exits 0 and creates one lead per record.
- AC-3.4: The skill's after-run steps tell the developer to run `cottonwood prospects-import FILE --check`, then `cottonwood prospects-import FILE`, then `cottonwood record-run` with `--skill research-prospects`, the skill's version, `--validation` from the check and `--cost` from Claude Code's `/cost` output with `--cost-source claude-code-cost`.

### US-4 — No sending credentials, and a written research routine
As the developer, I want a test that fails if an email-sending credential is committed and a runbook section for a research run, so that R-27 holds and the routine is repeatable.

Acceptance criteria:
- AC-4.1: A test reads every file `git ls-files` lists (skipping binary files) and fails, naming the file and line, if any line matches a sending-credential pattern: an assignment to a name containing `SMTP_PASS`, `SMTP_PASSWORD`, `SENDGRID_API_KEY`, `MAILGUN_API_KEY`, `POSTMARK_SERVER_TOKEN`, `SES_SECRET` or `MAIL_PASSWORD` with a non-empty value, or an `smtp://` / `smtps://` URL carrying a password; it passes on the current repository, and a unit test of the matcher shows each pattern caught and the `.env.example` comment lines not caught.
- AC-4.2: `docs/runbook.md` has a `## Research run` section listing, in order: start the `research-prospects` skill with a brief, note the start and end time, run `prospects-import FILE --check`, import, read `/cost`, and `record-run` with the cost source `claude-code-cost` (or `billing-console` and `--estimated` when the figure is not exact).
- AC-4.3: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

## Constraints & assumptions
- `record-run` writes only `agent_runs`; it writes no activity (agent_runs is its own audit table, architecture data model) and makes no network call.
- Times use the existing operator time forms (`YYYY-MM-DD HH:MM` in America/Denver, or UTC ending in `Z`) and are stored in UTC (R-32).
- Cost is a plain non-negative decimal with at most 4 places, stored as exact text; tokens a non-negative whole number; validation is `passed` or `failed`; the cost source is `claude-code-cost` or `billing-console` (R-26 names Claude Code's `/cost` output and the billing console).
- `--check` uses the same loader, validator and checklist keys as the import and writes nothing, not even `import_rejected` activities, so a check never counts as a data-quality failure.
- The skill's `version` frontmatter field is the skill version `record-run` records; Claude Code ignores frontmatter keys it does not use.
- The skill runs interactively in Claude Code; tests cannot run Claude, so they check the skill file's tools, rules and worked example instead of a live run.

## Success metrics
- The phase-4 exit criterion for this feature holds: the `research-prospects` skill's output format validates and imports, and a run is recorded with cost and source and shows in the report's model cost (roadmap phase 4).

## Open questions
- [Founder] Which geography, firm types and roles the first research briefs target; the skill takes them from the brief, not from config.
- [Developer] The monthly model-cost cap amount (config `model_cost_cap_usd`) is still unset; the report says so.
