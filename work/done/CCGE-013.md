# CCGE-013 — Runbook: restore and deletion-request procedures

## Goal
docs/runbook.md documents restoring a backup (with the suppression re-apply step) and handling deletion requests, and a test exercises the restore checks.

## Inputs
Spec: `work/specs/data-core/spec.md` (AC-4.1, AC-4.2, AC-4.3)
Plan: `work/specs/data-core/plan.md`

## Constraints
_None._

## Plan
1. Create docs/runbook.md with a short intro and sections `## Restore from backup`, `## Re-applying suppression after a restore`, `## Deletion requests`; leave clearly marked placeholders-free headings for the inbound sections inbound-logging adds later (no TODO text, just the three sections now).
2. Restore steps: run `cottonwood backup` first if the database opens; copy the current database aside to data/cottonwood.db.before-restore-<UTC>; copy the chosen backup into place; check it opens (`sqlite3 data/cottonwood.db 'PRAGMA integrity_check;'` returns ok) and contains the suppression table (`SELECT count(*) FROM suppression;`); run `cottonwood migrate`; re-apply suppression entries newer than the backup from the set-aside copy (SQL given).
3. Deletion steps: take a backup; clear name, email, email_norm, phone_e164, role, source_url and the person's notes in activities payloads are not edited (append a correction activity instead); set deleted_at; keep the suppression row (say so explicitly).
4. Add tests/test_runbook_restore.py: asserts the headings and key phrases exist, then performs the restore steps on scratch files with Python sqlite3/shutil (set aside, copy, integrity_check ok, suppression present, re-apply newer suppression rows) and asserts the result.
5. Run all checks.

## Acceptance Criteria
- [x] docs/runbook.md contains a `## Restore from backup` section whose steps, in order, set the current database aside, copy the backup into place, run `PRAGMA integrity_check`, query the suppression table, and run `cottonwood migrate`.
- [x] docs/runbook.md contains a `## Re-applying suppression after a restore` section with the SQL that copies suppression rows added after the backup from the set-aside database into the restored one.
- [x] docs/runbook.md contains a `## Deletion requests` section that says to take a backup first, clear the contact's personal fields, set deleted_at, and that the suppression entry is kept.
- [x] tests/test_runbook_restore.py performs the restore and suppression re-apply steps on scratch databases and asserts the restored database passes integrity_check, has the suppression table, and includes a suppression row added after the backup.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy .` exit 0.

All criteria verified 2026-11-15.

## Depends on
CCGE-012
