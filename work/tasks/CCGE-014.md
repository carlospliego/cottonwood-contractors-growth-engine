# CCGE-014 — Backup to an unwritable folder exits 1 instead of a traceback

## Goal
An OSError while claiming or writing the backup file becomes a BackupError, the claimed file is removed, and `cottonwood backup` exits 1 with `error: ...`.

## Inputs
cottonwood/backup.py:46-64,review finding F-correctness-3 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test runs `main(['backup', '--db', db, '--to', dir])` with dir made read-only (chmod 0o500) and asserts exit 1, an `error:` line on stderr naming the folder, and no traceback.

## Depends on
_None._
