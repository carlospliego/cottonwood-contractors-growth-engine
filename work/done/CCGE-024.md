# CCGE-024 — Test the default config/pilot.yaml path

## Goal
Exercise default_config_path when neither --config nor COTTONWOOD_CONFIG is set.

## Inputs
cottonwood/config.py:28-31,review finding F-testing-3 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test delenv's COTTONWOOD_CONFIG, chdirs to tmp_path, writes config/pilot.yaml with a backup_dir, runs `main(['backup', '--db', db])` and asserts the backup lands in that folder.

All criteria verified 2026-11-20.

## Depends on
_None._
