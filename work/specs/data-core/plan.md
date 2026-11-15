# Data Core — implementation plan

<!-- Written by /sir:plan from spec.md. Every decision traces to a story or constraint. -->

## Approach
**Context (Phase 0):**
- Migrations live in the package and run in order 001..N with no gaps; each runs under `BEGIN IMMEDIATE` with `user_version` re-checked (`cottonwood/db.py:56-78`, `95-116`). The only migration is `cottonwood/migrations/001_baseline.sql`, so the schema is `002_core.sql`.
- Subcommands register in `COMMANDS` as `Command(name, help, add_arguments, handler)`; handlers return 0/1 and print `error: …` to stderr (`cottonwood/cli.py:22-75`).
- Tables, key columns, the append-only `activities` table and the never-deleted `suppression` table are specified in `work/initiatives/cottonwood-growth-engine/architecture.md:57-79` and decisions 9-10 (`architecture.md:54-55`); stages per lead type are R-14 (`docs/cottonwood-growth-engine.md:44`).
- `config/pilot.yaml` and PyYAML are architecture decision 5 (`architecture.md:50`); backup requirement is R-33 and secrets/.env are R-34 (`docs/cottonwood-growth-engine.md:71-72`); deletion requests R-35 (`:73`).
- Existing tests that pin the schema at version 1 with the default migrations: `tests/test_migrate.py:48-50, 55, 65-66, 169, 184`.
- `.gitignore` already ignores `data/`, `*.db`; `.env` is not yet ignored.

The work is four tasks: shared helpers (no schema dependency), the schema migration plus a `connect()` helper, the config loader with the `backup` command, and the runbook sections with a test that executes the restore steps.

## Components & changes
| Area / file | Change | Serves |
|---|---|---|
| `cottonwood/timeutil.py` | `utc_now() -> str`, `to_utc_iso(datetime)`, `parse_utc(str)`, `display_local(str) -> str` (America/Denver with offset), `local_date(str) -> date`, `DENVER` ZoneInfo | US-2 |
| `cottonwood/normalize.py` | `normalize_email`, `normalize_phone` (E.164, default +1), `normalize_domain`, `normalize_name`; raise `ValueError` with the rule broken | US-2 |
| `pyproject.toml`, `uv.lock` | add `tzdata`, `PyYAML`; dev `types-PyYAML` | US-2, US-3 |
| `cottonwood/migrations/002_core.sql` | 7 tables, indexes, CHECKs (lead type, stage per type, eligibility, evidence kind), triggers: `activities` no UPDATE/DELETE, `suppression` no UPDATE/DELETE | US-1 |
| `cottonwood/db.py` | `connect(db_path) -> sqlite3.Connection` (foreign_keys ON, busy timeout, Row factory) | US-1 |
| `tests/test_migrate.py` | default-migration assertions move from version 1/no tables to version 2/the 7 tables | US-1 |
| `cottonwood/config.py` | `load_config(path=None) -> Config` from `config/pilot.yaml` (`COTTONWOOD_CONFIG` override); typed `backup_dir`; clear `ConfigError` | US-3 |
| `config/pilot.yaml` | `paths: {backup_dir: data/backups}` with comments | US-3 |
| `cottonwood/backup.py` + `backup` command in `cli.py` | `backup(db_path, dest_dir) -> Path` via `sqlite3.Connection.backup`; refuses missing folder / missing db | US-3 |
| `.env.example`, `.gitignore` | `.env.example` with no sending credentials; ignore `.env` | US-3 |
| `docs/runbook.md` | "Restore from backup", "Re-applying suppression after a restore", "Deletion requests" | US-4 |
| `tests/test_runbook_restore.py` | executes the documented restore checks against scratch files | US-4 |

## Data & interfaces
- **002_core.sql** columns follow `architecture.md:61-67`. Timestamps are TEXT UTC ISO-8601 (`…Z`). `leads.type` CHECK in (`inbound_inquiry`, `direct_candidate`, `relationship_prospect`); `leads.stage` CHECK: direct/inbound stages for the first two types, relationship stages for the third. `contacts.eligibility` CHECK in (`eligible`, `ineligible`, `unknown`) default `unknown`. `evidence.kind` CHECK in (`fact`, `hypothesis`). `organizations.domain_norm` UNIQUE where not null (partial index). `leads.referred_by` → `leads.id`; `activities.voids_activity_id` → `activities.id`; `leads.is_test` INTEGER 0/1 default 0. `activities.payload` TEXT JSON (CHECK `json_valid`).
- **Triggers:** `BEFORE UPDATE ON activities` and `BEFORE DELETE ON activities` → `RAISE(ABORT, 'activities are append-only')`; same for suppression with `'suppression entries are never deleted or changed'`.
- **CLI:** `cottonwood backup [--db PATH] [--to DIR] [--config PATH]` → prints `backup written: <path>`; exit 1 with `error: backup folder does not exist: <dir>` or `error: database does not exist: <path>`.
- **Backup name:** `cottonwood-YYYYMMDDTHHMMSSZ.db`; if that name exists, a `-2`, `-3` … suffix is added rather than overwriting.
- **Config:** YAML mapping; unknown keys ignored; relative paths resolve against the current directory.

## Risks & rollback
| Risk | Mitigation | Rollback |
|---|---|---|
| Triggers block a legitimate later need (e.g. correcting a typo) | R-17 defines corrections as new void activities, not edits | Additive migration; revert the PR before real data exists |
| zoneinfo missing tz data | `tzdata` dependency | — |
| Backup taken while another process writes | SQLite backup API copies a consistent snapshot | Re-run backup |
| Restore test depends on the `sqlite3` CLI | Test uses Python's `sqlite3` module for the same checks | — |

## Test strategy
| AC | How | Command |
|---|---|---|
| AC-1.1 | migrate a tmp db; inspect `sqlite_master` and `PRAGMA table_info` per table | `uv run pytest tests/test_schema.py` |
| AC-1.2, 1.3 | insert rows, attempt UPDATE/DELETE, assert `sqlite3.IntegrityError`, re-read the row | `uv run pytest tests/test_schema.py` |
| AC-1.4 | parametrized insert of every allowed type/stage pair and some forbidden ones | `uv run pytest tests/test_schema.py` |
| AC-1.5 | db at version 1 (baseline only) → migrate → version 2; migrate again → applied 0 | `uv run pytest tests/test_schema.py tests/test_migrate.py` |
| AC-2.x | unit tests with fixed instants (2026-03-08 DST start, 2026-11-01 DST end) and normalization tables | `uv run pytest tests/test_timeutil.py tests/test_normalize.py` |
| AC-3.x | tmp db with suppression rows → backup → open copy; missing folder; missing db; config/env override; `git check-ignore .env data/backups/x.db` | `uv run pytest tests/test_backup.py` |
| AC-4.1, 4.2 | read runbook headings and required phrases | `uv run pytest tests/test_runbook_restore.py` |
| AC-4.3 | follow the restore steps with Python `sqlite3`/`shutil` on scratch files | `uv run pytest tests/test_runbook_restore.py` |
| all | full checks | `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` |

## Sequencing
1. T-01 helpers (independent; adds tzdata).
2. T-02 schema + `connect()` (needs nothing from T-01, but runs after it to keep one lockfile change at a time).
3. T-03 config + backup (backup test uses the suppression table from T-02).
4. T-04 runbook + restore test (uses `backup` from T-03).
