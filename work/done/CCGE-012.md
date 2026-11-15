# CCGE-012 — Config loader and backup command

## Goal
`cottonwood backup` copies the database with the SQLite backup API into the backup folder from config/pilot.yaml under a timestamped name; .env.example is committed and .env ignored.

## Inputs
Spec: `work/specs/data-core/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-3.4)
Plan: `work/specs/data-core/plan.md`

## Constraints
_None._

## Plan
1. Add PyYAML to dependencies and types-PyYAML to the dev group; commit uv.lock.
2. Add config/pilot.yaml with paths.backup_dir: data/backups and comments; add cottonwood/config.py with load_config(path=None) reading $COTTONWOOD_CONFIG or config/pilot.yaml, returning a frozen Config(backup_dir: Path); ConfigError on a missing file, invalid YAML or a non-string backup_dir.
3. Add cottonwood/backup.py: backup(db_path, dest_dir) -> Path; refuse a missing dest folder (BackupError naming it) and a missing database; name cottonwood-<UTC YYYYMMDDTHHMMSSZ>.db with -2, -3 suffix on collision; copy with sqlite3 backup API.
4. Register `backup` in cli.py with --db, --to, --config; print `backup written: <path>`; exit 1 with `error: ...` on BackupError/ConfigError.
5. Add .env.example (comment that no email-sending credentials belong here) and `.env` to .gitignore.
6. Add tests/test_backup.py; run all checks.

## Acceptance Criteria
- [x] A test migrates a temp database, inserts a suppression row, runs `main(['backup', '--db', db, '--to', dir])`, and asserts exit 0, a printed path matching cottonwood-\d{8}T\d{6}Z(-\d+)?\.db inside dir, and that the copy has user_version 2 and the suppression row.
- [x] A test asserts backup to a folder that does not exist exits 1, prints that folder path on stderr, and creates nothing.
- [x] A test asserts backup of a database path that does not exist exits 1 and names the path.
- [x] A test shows that without --to the folder comes from paths.backup_dir in the YAML file named by COTTONWOOD_CONFIG.
- [x] config/pilot.yaml exists with paths.backup_dir set to data/backups.
- [x] .env.example is tracked, `git check-ignore .env` and `git check-ignore data/backups/x.db` both succeed, and `grep -riE 'smtp|sendgrid|mailgun|api_key|password' .env.example config/` finds no credential values.
- [x] Two backups taken in the same second produce two distinct files (the second gets a -2 suffix), and a test asserts it.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy .` exit 0.

All criteria verified 2026-11-15.

## Depends on
CCGE-011
