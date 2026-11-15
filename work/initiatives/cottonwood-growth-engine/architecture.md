# Cottonwood Growth Engine — architecture

Source: `docs/cottonwood-growth-engine.md` (R-n refers to its requirements). Project: `project.md`.

## Context (current system, cited from the code)
- There is no application code yet. Tracked files are the sir scaffold: `CLAUDE.md`, `.sir/config.yaml`, `.sir/policy.yaml`, `work/todo.md`, `.claude/settings.json`, `.gitignore`, `README.md`, plus the spec `docs/cottonwood-growth-engine.md`.
- `.sir/config.yaml:11-16` has every check (`test`, `lint`, `typecheck`, `build`, `format`) set to `null`. The scaffold feature has to create commands for them, and `/sir:init` must re-run afterwards.
- `.claude/settings.json` sandboxes Bash, with network limited to GitHub hosts. Installing Python packages from PyPI needs `pypi.org` and `files.pythonhosted.org` added to `sandbox.network.allowedDomains`, or the installs have to run outside the sandbox.
- External systems that already exist, outside this repo: the live website at cottonwoodcontractors.com, the Formspark form backend, Cottonwood's business mailbox and phone. The tool reads none of them programmatically.

## Target design
One local Python package with a single CLI entry point, one SQLite file, two Claude Code project skills, and Markdown output files.

```
cottonwood/                 Python package (CLI entry point: `cottonwood`)
  cli.py                    argument parsing → one function per command
  db.py                     connection, migrations runner (PRAGMA user_version), UTC time helpers
  normalize.py              email / E.164 phone / domain / name normalization (dedupe + suppression keys)
  validate.py               research-record and skill-output schemas (R-5, R-6, R-20, R-25)
  inbound.py                log-inbound, duplicate check (R-1–R-3)
  prospects.py              prospects-import, set-eligibility, mark-reviewed (R-5–R-12)
  events.py                 log-event, stages, corrections (R-14–R-17)
  gate.py                   approve, claims, prepare-send, log-outreach, log-reply, suppress (R-18–R-24)
  runs.py                   record-run for Claude skill runs (R-26)
  review.py / report.py     review queues and the Markdown report (R-13, R-28–R-31)
  backup.py                 SQLite backup API copy (R-33)
db/migrations/NNN_*.sql     plain SQL, applied in order
config/pilot.yaml           Cottonwood values: checklist items, evidence max age, caps, sender identity, postal address, paths
config/claims.yaml          the claims library (R-19)
schemas/*.json              JSON Schemas for research records and drafting-skill output
.claude/skills/research-prospects/SKILL.md     runtime skill: research → schema-valid JSON file
.claude/skills/prepare-outreach/SKILL.md       runtime skill: draft + claims list + founder brief
docs/runbook.md             inbound checklist, relay, restore, deletion requests (R-4, R-33, R-35)
tests/                      pytest; fixtures are synthetic and labeled
out/                        generated review/report/draft files (git-ignored: they contain contact data)
```

**Data flow:**
1. Skills write JSON files under `out/`.
2. The CLI validates and imports those files, so Claude never writes to the database directly.
3. Every write appends an `activities` row.
4. `prepare-send` is the only producer of a sendable draft file.
5. `report` and `review` read the database and write Markdown to `out/`.

## Key decisions (ADR-style: decision, alternatives, why)
1. **SQLite through the standard library `sqlite3`**, rather than PostgreSQL or an ORM. There's one operator and low volume, and backup can use the built-in backup API. *Why:* nothing to run or install, which fits 10–20 developer hours a week. (Spec decision.)
2. **Plain SQL migrations with a `PRAGMA user_version` runner**, rather than Alembic or another migration tool. *Why:* one database and a few tables; a 30-line runner is easier to audit than a framework.
3. **CLI with the standard library `argparse`**, rather than Click or Typer. *Why:* about 20 subcommands with simple flags; no dependency; easy to test by calling `main(argv)`.
4. **Validation with `jsonschema` against files in `schemas/`**, rather than pydantic models. *Why:* the same schema file goes into the Claude skill's instructions, so the skill and the validator share one definition. Errors name the field and rule (R-6).
5. **Config in YAML (`PyYAML`)**, rather than TOML or a database table. *Why:* the founder-facing values (claims, checklist items) are easy to read and diff, and changes show up in git history.
6. **Claude skills are file-in/file-out and hold no credentials**, rather than skills that call the CLI or the database. *Why:* this enforces R-21/R-27. The skill can only produce a file, and the deterministic CLI decides what gets imported or sent.
7. **The skill run is recorded by the developer** (`cottonwood record-run` with cost taken from Claude Code's `/cost` output), rather than hooks that capture cost automatically. *Why:* run caps are record-only (spec decision), and interactive runs expose cost only through `/cost` or the billing console.
8. **Tooling: `uv` for the environment, `pytest`, `ruff` for lint and format, `mypy` for typecheck**, rather than pip with flake8/black. *Why:* fast, a single config in `pyproject.toml`, and they give the four sir checks real commands.
9. **Approvals, events, sends, replies and corrections are rows in one append-only `activities` table**, rather than separate tables. *Why:* keeps the schema at about 7 tables (spec decision) and gives one audit trail.
10. **Suppression is a separate table keyed on the normalized email, never deleted.** It is checked in `prospects-import`, `set-eligibility`, the skill input step and `prepare-send` (R-24). *Why:* one deterministic choke point, kept separate from contact rows, which can be deleted on request (R-35).

## Interfaces & data
**Tables** (`db/migrations/001_init.sql`):
| Table | Key columns |
|---|---|
| organizations | id, name, name_norm, domain_norm (unique where not null), type, category, created_at |
| contacts | id, organization_id, name, email, email_norm, phone_e164, role, source_url, eligibility (`eligible`/`ineligible`/`unknown`), deleted_at |
| leads | id, type (`inbound_inquiry`/`direct_candidate`/`relationship_prospect`), organization_id, contact_id, stage (CHECK per type, R-14), segment, channel, property_location, hypothesis, next_action, founder_time_h, value_amount (TEXT decimal), value_basis, referred_by (lead id), is_test, received_at |
| evidence | id, lead_id, url, observed_at, published_at, excerpt, kind (`fact`/`hypothesis`), source_status |
| activities | id, lead_id, contact_id, type, payload JSON, actor, occurred_at, recorded_at, voids_activity_id. Append-only: triggers reject UPDATE and DELETE |
| agent_runs | id, skill, skill_version, model, started_at, ended_at, input_ref, output_ref, validation, tokens, cost_usd, cost_source, cost_estimated |
| suppression | email_norm (primary key), reason, source, added_at |

**Activity types:**
- Inbound: `inquiry_logged`
- Imports: `imported`, `import_rejected`
- Contacts and review: `eligibility_set`, `hand_review`
- Approvals and claims: `approval`, `claim_verified`
- Sending: `draft_prepared`, `prepare_refused`, `sent`, `gate_violation`
- Replies: `reply`, `suppressed`
- Events: the R-15 event types
- `stage_change`, `correction`

**Commands:** `log-inbound`, `prospects-import`, `set-eligibility`, `mark-reviewed`, `review`, `log-event`, `approve`, `prepare-send`, `log-outreach`, `log-reply`, `suppress`, `record-run`, `report`, `log-time`, `log-cost`, `backup`, `migrate`.

- Exit codes: 0 = done, 1 = refused (a gate or validation failure, with a message naming each failed check), 2 = usage error.

**Skill I/O:**
- `research-prospects` writes `out/research/<date>-<slug>.json`, validated against `schemas/research-record.schema.json`.
- `prepare-outreach` reads one lead export (`cottonwood review --lead <id> --json`) and writes:
  - `out/drafts/<lead>-<n>.md`, the draft;
  - `out/drafts/<lead>-<n>.claims.json`, validated against `schemas/draft-claims.schema.json`;
  - `out/briefs/<lead>-<n>.md`, the founder brief.

## Non-functional requirements (numbers)
- **Cost:** recurring ≤ $500/month in total (spec). Model cost is recorded per run, and the report shows month-to-date spend against the cap.
- **Operator time:** the daily logging routine, covering the relay inbox and the call note, should take ≤ 15 developer minutes on a typical day. This is a proposed target, measured with `log-time` in week 1.
- **Speed (proposed):** every CLI command finishes in ≤ 2 s on a database of 10,000 leads. The full test suite runs in ≤ 60 s on the developer's machine.
- **Durability:** a `backup` copy is consistent (SQLite backup API), and the restore procedure is rehearsed once before the first real send.
- **Network:** the CLI makes no network calls. Only Claude Code skill runs use the network.
- **Privacy:** contact data lives only in the SQLite file, the backups and `out/`, all git-ignored, on a FileVault-encrypted disk. No email-sending credentials exist anywhere in the repo or its config (R-27).
- **Time:** stored in UTC and displayed in America/Denver (R-32).
- **Correctness gates:** each `prepare-send` refusal reason and each R-n with a behavior has a pytest test on labeled synthetic fixtures.
