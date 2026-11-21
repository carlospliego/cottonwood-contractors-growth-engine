# CCGE-019 — paths.backup_dir expands ~ and trims spaces

## Goal
load_config returns Path(backup_dir.strip()).expanduser() so '~/backups' and ' data/backups ' work as expected.

## Inputs
cottonwood/config.py:62-65,review finding F-correctness-9 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test with HOME set to tmp_path asserts backup_dir '~/b' loads as tmp_path / 'b', and ' data/backups ' loads as Path('data/backups').

All criteria verified 2026-11-20.

## Depends on
_None._
