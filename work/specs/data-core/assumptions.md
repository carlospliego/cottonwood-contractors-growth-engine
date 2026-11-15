# Assumptions — data-core

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** How is phase 2 split between data-core and inbound-logging?
- **Answer:** data-core: the 7-table migration with its triggers, time and normalization helpers, backup, .env.example, and the runbook restore and deletion-request sections. inbound-logging: log-inbound, the duplicate check, review, and the runbook inbound checklist and relay sections.
- **Why:** The roadmap lists both features for phase 2 without dividing the exit criteria; the storage foundations must exist before inbound logging can use them.

## A-2 · plan
- **Question:** Normalize phone numbers with the phonenumbers package or by hand?
- **Answer:** By hand: US numbers to +1 E.164, plus +-prefixed international numbers of 8-15 digits
- **Why:** Cottonwood serves four Utah counties; a small rule set avoids a large dependency and is easy to test.

## A-3 · plan
- **Question:** Where does the 'configured local backup folder' come from?
- **Answer:** config/pilot.yaml paths.backup_dir (default data/backups, git-ignored), file path overridable with COTTONWOOD_CONFIG, and --to for one run; PyYAML reads it
- **Why:** architecture.md puts paths in config/pilot.yaml and picks YAML via PyYAML (decision 5).

## A-4 · plan
- **Question:** Which writes do the SQL triggers block, and is the activity type constrained in SQL?
- **Answer:** activities rejects UPDATE and DELETE; suppression rejects DELETE and UPDATE; activities.type is free text validated by the commands
- **Why:** R-17 and R-24 forbid edits and deletion; a CHECK on activity types would force a migration for every new event type.

## A-5 · plan
- **Question:** How is the America/Denver zone resolved?
- **Answer:** zoneinfo with the tzdata package as a dependency
- **Why:** Guarantees the zone exists on any machine without relying on the OS tz database.

## A-6 · plan
- **Question:** How are foreign keys and contact deletion handled?
- **Answer:** A shared connect() helper turns on PRAGMA foreign_keys; contacts are soft-deleted (deleted_at) with their personal fields cleared, and the suppression row stays
- **Why:** R-35 removes personal data but keeps suppression; leads and activities still reference the contact row.

## A-7 · do CCGE-012
- **Question:** Should `cottonwood backup --to DIR` still load config/pilot.yaml, and which wins between --config and $COTTONWOOD_CONFIG?
- **Answer:** The config is loaded only when --to is absent; --config takes precedence over $COTTONWOOD_CONFIG, which takes precedence over config/pilot.yaml.
- **Why:** Surveyor's recommendation: an explicit --to needs no config, so backup works from any directory; explicit flags beat environment, matching --db over $COTTONWOOD_DB.

## A-8 · do CCGE-013
- **Question:** R-35 and AC-4.2 say a deletion request removes the person's notes, but contacts has no notes column and activity payloads cannot be edited or deleted (append-only triggers, R-17). What should the runbook promise?
- **Answer:** The runbook says plainly that past activity payloads are not edited: the founder clears the contact fields, sets deleted_at, appends a `correction` activity recording the request, and keeps the suppression row. It flags that notes inside old activity payloads stay, as an open conflict between R-35 and R-17 for the founder to resolve.
- **Why:** Surveyor's recommendation; the contract's plan step 3 already says not to edit payloads, and promising removal the schema forbids would be wrong.
