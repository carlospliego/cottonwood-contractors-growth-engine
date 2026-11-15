# Inbound Logging — implementation plan

<!-- Written by /sir:plan from spec.md. Every decision traces to a story or constraint. -->

## Approach
**Context (Phase 0):**
- CLI commands register in the `COMMANDS` table with an `add_arguments` function and a handler returning 0 (done), 1 (refused) or 2 (usage) (cottonwood/cli.py:1-4, cottonwood/cli.py:95-108). New commands follow the `migrate`/`backup` pattern: `--db` defaulting to `db.default_db_path()` (cottonwood/cli.py:33-52).
- `db.connect()` opens an existing file with foreign keys on and the Row factory, raising `DatabaseMissingError` for a missing file (cottonwood/db.py:58).
- `leads` already has type, stage (R-14 CHECK), segment, channel, property_location, value_amount/value_basis, is_test and received_at, but no scope column (cottonwood/migrations/002_core.sql:36-64). `contacts` holds name, email, email_norm, phone_e164 with indexes on email_norm and phone_e164 (cottonwood/migrations/002_core.sql:18-33). `organizations` needs name, name_norm, created_at (cottonwood/migrations/002_core.sql:4-12). `activities` is append-only, payload JSON (cottonwood/migrations/002_core.sql:80-110).
- Helpers exist: `normalize_email`, `normalize_phone`, `normalize_name` (cottonwood/normalize.py:14,27,65), `to_utc_iso`, `utc_now`, `parse_utc`, `display_local`, `local_date`, `DENVER` (cottonwood/timeutil.py:9-45).
- Migrations are numbered `NNN_name.sql` files applied in order by `db.migrate` (cottonwood/db.py:18,147); tests assert the newest version is 2 (tests/test_migrate.py:59, tests/test_schema.py:161, tests/test_runbook_restore.py:114).
- The runbook says later features add the inbound checklist and relay sections (docs/runbook.md:8).

**Design.** A new module `cottonwood/inbound.py` holds the inquiry model, validation, the duplicate query and the insert, as pure functions over a `sqlite3.Connection`, so tests drive them directly and through `cli.main`. All writes for one inquiry (organization, contact, lead, activity) happen in one transaction: validation and the duplicate check run first, and nothing is written on refusal. A new module `cottonwood/review.py` reads inquiries and renders Markdown; it exposes `counted_inquiries_filter` (`is_test = 0`) for the future report. The CLI gains `log-inbound` and `review` entries in `COMMANDS`.

## Components & changes
| Area / file | Change | Serves |
|---|---|---|
| cottonwood/migrations/003_inbound.sql | `ALTER TABLE leads ADD COLUMN project_scope TEXT` | US-1 |
| cottonwood/timeutil.py | `parse_received(value) -> str`: accepts `YYYY-MM-DD HH:MM` America/Denver local (fold=0 for ambiguous times) or a UTC ISO string; returns stored UTC | US-1 |
| cottonwood/inbound.py | `Inquiry` dataclass, `validate`, `find_same_day_duplicates(conn, email_norm, phone_e164, received_at)`, `log_inquiry(conn, inquiry, confirmed_duplicates)` | US-1, US-2 |
| cottonwood/cli.py | `log-inbound` (flags below; prompt via `input()` only when `sys.stdin.isatty()`), `review [--out PATH]` | US-1, US-2, US-3 |
| cottonwood/review.py | `inbound_rows(conn)`, `inbound_counts(conn)`, `render_review(conn) -> str` | US-3 |
| docs/runbook.md | `## Inbound verification checklist` table and `## Relay` section; drop line 8 | US-4 |
| tests/test_inbound.py, tests/test_inbound_duplicates.py, tests/test_review.py, tests/test_runbook_inbound.py | new tests | all |
| tests/test_migrate.py, tests/test_schema.py, tests/test_runbook_restore.py | newest version 2 → 3 | US-1 |

## Data & interfaces
- `cottonwood log-inbound --channel {form,phone} --received WHEN --segment {commercial,residential,unknown} [--name] [--email] [--phone] [--company] [--location] [--scope] [--budget DECIMAL] [--test] [--confirm-duplicate] [--actor developer] [--db PATH]`.
  - Success prints `logged inquiry lead <id> (<channel>, <segment>, received <display_local>)` plus ` TEST` for tests; exit 0.
  - Duplicate: stderr `warning: possible duplicate of lead(s) <ids> received <local date>`; then prompt `Save anyway? [y/N] ` on a TTY, else refuse unless `--confirm-duplicate`; refusal exit 1.
- Budget: `decimal.Decimal`, finite and ≥ 0, stored as its normalized string (`str(Decimal)`), basis `buyer-stated`.
- Organization: `SELECT id FROM organizations WHERE name_norm = ? ORDER BY id LIMIT 1`, else insert (name, name_norm, created_at = utc_now()).
- Lead: type `inbound_inquiry`, stage `candidate`; contact row with name, email, email_norm, phone_e164.
- Activity `inquiry_logged`: actor, occurred_at = received_at, recorded_at = utc_now(), payload `{"channel", "segment", "is_test", "duplicate_of": [ids]}` (no personal data).
- Duplicate query: inbound_inquiry leads joined to contacts where `(email_norm = ? OR phone_e164 = ?)` and `local_date(received_at)` equals the new inquiry's local date (filtered in Python over the matches).
- `cottonwood review [--out PATH] [--db PATH]`: Markdown starting `# Review`, generated time, then `## Inbound inquiries`, the count line `Inquiries: N (form a, phone b; commercial c, residential d, unknown e). Test inquiries excluded: M.`, then a table `| Lead | Received | Channel | Segment | Stage | Name | Email | Phone | Company | Location | Scope | Budget | Label |`. Markdown pipes in values are escaped.

## Risks & rollback
| Risk | Mitigation | Rollback |
|---|---|---|
| Migration 003 breaks an existing database | `ADD COLUMN` of a nullable column is non-destructive; take `cottonwood backup` before migrating | restore the backup per the runbook |
| Ambiguous/nonexistent local times at DST changes | `parse_received` uses fold=0 and documents it; UTC `Z` input avoids it | — |
| Review file leaks contact data into git | default suggestion `out/`, which is git-ignored | delete the file |
| A prompt hangs in scripts | prompt only when stdin is a TTY | `--confirm-duplicate` |

## Test strategy
All via pytest on temporary databases (`UV_OFFLINE=1 UV_NO_SYNC=1 uv run pytest <file>`), checks with `uv run ruff check .`, `uv run mypy .`, `uv run ruff format --check .`.
- AC-1.1: tests/test_inbound.py migrates and reads `PRAGMA table_info(leads)`; version tests updated to 3.
- AC-1.2–1.7: tests/test_inbound.py calls `cli.main([...])` and inspects rows.
- AC-2.1–2.4: tests/test_inbound_duplicates.py; TTY cases monkeypatch `sys.stdin.isatty` and `builtins.input`.
- AC-3.1–3.5: tests/test_review.py renders output for seeded inquiries and checks rows, labels, counts and `--out`.
- AC-4.1–4.3: tests/test_runbook_inbound.py asserts headings and each checklist item with its three fields; existing runbook tests still pass.

## Sequencing
T-01 (migration, timeutil, log-inbound) first: everything else reads its rows. T-02 (duplicate check) extends log-inbound. T-03 (review) needs logged inquiries. T-04 (runbook) documents the finished commands.
