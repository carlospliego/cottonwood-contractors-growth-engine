# CCGE-002 — Migrations runner and migrate command

## Goal
`cottonwood migrate` creates or upgrades a SQLite file through ordered NNN_*.sql migrations tracked with PRAGMA user_version.

## Inputs
Spec: `work/specs/scaffold/spec.md` (AC-2.1, AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5)
Plan: `work/specs/scaffold/plan.md`

## Constraints
_None._

## Plan
1. Add db/migrations/001_baseline.sql (comment only, creates no tables).
2. Add cottonwood/db.py: MIGRATIONS_DIR (repo db/migrations), default_db_path() reading COTTONWOOD_DB else data/cottonwood.db, discover_migrations(dir) returning (number, path) sorted and rejecting duplicate numbers, migrate(db_path, migrations_dir) applying each migration with number > user_version in its own transaction and setting user_version, returning (from_version, to_version). Raise a clear error when the parent folder is missing, before connecting.
3. Add the migrate subcommand in cottonwood/cli.py with --db; print the version line; return 1 with `error: folder does not exist: <dir>` on a missing folder.
4. Add tests/test_migrate.py: fresh file at version 1 with no tables; second run applies nothing; two temp migrations applied in order; missing folder exits 1, names it and creates nothing; COTTONWOOD_DB and the data/cottonwood.db default; the CLI lists migrate in --help.
5. Run all four checks.

## Acceptance Criteria
- [x] `uv run cottonwood --help` output contains `migrate`.
- [x] `uv run cottonwood migrate --db` pointed at a path that does not exist yet exits 0 and creates a SQLite file whose `PRAGMA user_version` is 1 and whose sqlite_master has no rows for tables other than names starting with `sqlite_`.
- [x] Running migrate a second time on the same file exits 0 and leaves user_version unchanged, and a test asserts it.
- [x] A test with a temporary migrations directory holding two NNN_*.sql files shows both applied in numeric order and user_version set to the higher number; a file whose number is <= the current user_version is not applied.
- [x] When the --db parent folder does not exist, migrate exits 1, prints a message containing that folder path, and creates no file; a test asserts all three.
- [x] Without --db, migrate uses COTTONWOOD_DB when set and data/cottonwood.db otherwise, each shown by a test; `git check-ignore data/cottonwood.db` succeeds.
- [x] `uv run pytest` exits 0 and includes tests in both tests/test_cli.py and tests/test_migrate.py.
- [x] `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` exit 0.

All criteria verified 2026-11-15.

## Depends on
CCGE-001
