# CCGE-103 — Review checklists in config, migration 005 and checklist answers in research records

## Goal
Keep each queue's checklist items in config/pilot.yaml and let research records carry yes/no/unknown answers that prospects-import validates against those items and stores on the lead.

## Inputs
Spec: `work/specs/prospect-review/spec.md` (AC-4.1, AC-4.2, AC-4.3)
Plan: `work/specs/prospect-review/plan.md`

## Constraints
- prospects-import loads the config like other commands: an explicit --config that does not exist is an error (exit 1); when no --config is given and the default config file is missing, it falls back to empty checklists, so every checklist key is rejected.
- Re-import differences: a checklist key whose stored answer is absent and whose incoming answer is present prints a checklist.KEY differs line (stored shown empty), like other fields.
- validate_record keeps working for existing callers: the allowed-checklist-keys parameter has an empty default.

## Plan
1. cottonwood/config.py: ChecklistItem, ReviewConfig (checklists per lead type, max_evidence_age_days), Config.review defaulting to empty checklists and no max age; validate review.checklists.<type> as a list of {key, label} (non-empty strings, key ^[a-z][a-z0-9_]*$, no duplicate key per queue) and review.max_evidence_age_days as a positive int (bool refused), raising ConfigError with the key path.
2. config/pilot.yaml: review block with the six direct_candidate and five relationship_prospect items from SPEC.md section 9 (founder time excluded) and a commented-out max_evidence_age_days.
3. cottonwood/migrations/005_review.sql: ALTER TABLE leads ADD COLUMN checklist TEXT; move the tests pinning schema version 4 to 5 (and the shipped-migrations list).
4. Schema: optional checklist object (property names match the key pattern, values enum yes/no/unknown). validate.py: validate_record takes the allowed keys per record type; an unconfigured key is rejected 'checklist.KEY: checklist-item', a bad value 'checklist.KEY: enum'; CSV columns named checklist.KEY (empty cell = absent); ProspectRecord.checklist.
5. prospects.py: store the checklist as sorted JSON object text (NULL when absent); _differences adds a checklist.KEY pair per incoming key. cli.py: prospects-import loads the config (existing --config option) and passes the allowed keys.
6. New tests: tests/test_review_config.py, tests/test_prospects_checklist.py.

## Acceptance Criteria
- [x] config/pilot.yaml loads with load_config into review.checklists holding 6 direct_candidate and 5 relationship_prospect items, each with a non-empty key matching ^[a-z][a-z0-9_]*$ and a non-empty label, and review.max_evidence_age_days None.
- [x] load_config raises ConfigError whose message names the offending path for each of: review.checklists.direct_candidate not a list; an item without a key; an item with an empty label; key 'Direct-Signal'; two items with key 'fit' in one queue; review.max_evidence_age_days 0, -5, 'ninety' and true.
- [x] Importing a direct_candidate JSON record whose checklist is {"direct_signal": "yes", "buyer_identified": "no"} (both configured keys in the test config) exits 0 and stores leads.checklist as the JSON object text {"buyer_identified": "no", "direct_signal": "yes"}; a record without checklist stores NULL.
- [x] A record with checklist {"direct_signal": "maybe"} is rejected with stderr line 'rejected record 1: checklist.direct_signal: enum', and one with checklist {"not_an_item": "yes"} is rejected 'rejected record 1: checklist.not_an_item: checklist-item'; neither writes a lead.
- [x] A CSV with a column checklist.direct_signal whose cell is 'yes' stores the same leads.checklist as the equivalent JSON record.
- [x] Re-importing a matched lead whose stored checklist has direct_signal 'yes' with incoming direct_signal 'no' prints a line containing 'checklist.direct_signal differs' and 'kept stored', and leads.checklist is unchanged.
- [x] After cottonwood migrate on a fresh database, PRAGMA user_version is 5 and leads has a checklist column.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._

## Tests to change
- `tests/test_backup.py`
- `tests/test_inbound.py`
- `tests/test_migrate.py`
- `tests/test_runbook_restore.py`
- `tests/test_schema.py`
- `tests/test_prospects_validate.py`
