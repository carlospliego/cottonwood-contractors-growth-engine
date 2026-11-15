# CCGE-023 — Test load_config fallback and empty-value branches

## Goal
Cover load_config's documented fallback to data/backups and its empty/null branches.

## Inputs
cottonwood/config.py:50-61,review finding F-testing-2 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Tests assert: an empty file, 'paths:' with no value and a mapping without backup_dir each load as Path('data/backups'); backup_dir '' and '  ' each raise ConfigError.

## Depends on
_None._
