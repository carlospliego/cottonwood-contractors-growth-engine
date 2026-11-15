# Data Core — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Phase 2 of the roadmap (`work/initiatives/cottonwood-growth-engine/roadmap.md:10`) needs a durable store before any inquiry, prospect or send is logged. Today `cottonwood migrate` only creates an empty versioned file (`cottonwood/migrations/001_baseline.sql`), so there is nowhere to record leads, an audit trail that cannot be altered, a suppression list that cannot shrink, or a way to back the database up and restore it. Losing or silently editing this data would break the spec's core promises: suppressed people are never contacted again (R-24), activities are never edited (R-17), and a consistent backup exists (R-33). It is solved when a fresh database migrates to all 7 tables with those protections enforced by SQLite itself, `cottonwood backup` writes a consistent timestamped copy, and `docs/runbook.md` explains restore and deletion requests.

## Goals / non-goals
- Goal: one additive migration creating the 7 tables from `architecture.md` (organizations, contacts, leads, evidence, activities, agent_runs, suppression) with the stage rule of R-14 and the append-only rules of R-17 and R-24 enforced in SQL.
- Goal: shared helpers later features use: UTC timestamps displayed in America/Denver (R-32), and email / E.164 phone / domain / name normalization (dedupe and suppression keys, R-2, R-24).
- Goal: `cottonwood backup` (R-33) reading its folder from `config/pilot.yaml`, and `.env.example` committed (R-34).
- Goal: `docs/runbook.md` with the restore procedure (R-33) and the deletion-request procedure (R-35).
- Non-goal: `log-inbound`, the duplicate check, `review`, and the runbook's inbound checklist and relay sections — the `inbound-logging` feature builds those.
- Non-goal: a restore command (project.md lists it as out of scope); restore is a documented manual procedure.
- Non-goal: any other subcommand (`suppress`, `log-event`, imports) — later phases.

## User stories
### US-1 — The schema exists and protects itself
As the developer, I want `cottonwood migrate` to create every table the tool needs, with SQLite rejecting edits that the spec forbids, so that no code path or manual query can rewrite the audit trail or shrink the suppression list.

Acceptance criteria:
- AC-1.1: On a fresh database, `cottonwood migrate` leaves `PRAGMA user_version` at 2 and creates exactly the tables organizations, contacts, leads, evidence, activities, agent_runs and suppression, each with the key columns listed in `architecture.md` (Interfaces & data).
- AC-1.2: An UPDATE or DELETE on any `activities` row fails with a SQLite error and leaves the row unchanged.
- AC-1.3: A DELETE on any `suppression` row fails with a SQLite error and leaves the row in place.
- AC-1.4: Inserting a lead whose stage is not allowed for its type (R-14: direct and inbound stages for `inbound_inquiry` and `direct_candidate`, relationship stages for `relationship_prospect`) fails; every allowed type/stage pair inserts.
- AC-1.5: Migrating a database already at version 1 (the scaffold baseline) to version 2 keeps working, and running `migrate` again applies nothing.

### US-2 — Shared time and normalization helpers
As the developer, I want one place that stores times in UTC, displays them in America/Denver, and normalizes contact keys, so that dedupe, suppression and reports agree on what "the same person" and "the same day" mean.

Acceptance criteria:
- AC-2.1: A UTC timestamp helper returns ISO-8601 strings ending in `Z` with second precision, and a display helper renders a stored UTC string in America/Denver with its offset (MST −07:00 in winter, MDT −06:00 in summer), shown by tests on fixed instants on both sides of a DST change.
- AC-2.2: A local-date helper returns the America/Denver calendar date of a UTC instant (e.g. 2026-11-16T05:30:00Z is 2026-11-15 in Denver).
- AC-2.3: Email normalization trims and lower-cases (`  Jane.Doe@Example.COM ` → `jane.doe@example.com`) and rejects strings without exactly one `@` and a dotted domain.
- AC-2.4: Phone normalization returns E.164 for US numbers written with spaces, dashes, dots, parentheses or a leading `1`/`+1` (`(801) 555-0134` → `+18015550134`), keeps a `+`-prefixed international number of 8–15 digits, and rejects anything else.
- AC-2.5: Domain normalization lower-cases, strips a scheme, `www.`, path, port and trailing dot (`https://WWW.Example.com:443/about` → `example.com`); name normalization lower-cases, collapses whitespace and strips punctuation for matching.

### US-3 — Consistent backups
As the developer, I want `cottonwood backup` to copy the live database consistently into the configured backup folder under a timestamped name, so that a restore after a mistake loses nothing that was committed.

Acceptance criteria:
- AC-3.1: `cottonwood backup` writes `<backup_dir>/cottonwood-<YYYYMMDDTHHMMSSZ>.db` using the SQLite backup API, exits 0 and prints the path; the copy opens, has the same `user_version` and contains the `suppression` table and its rows.
- AC-3.2: When the configured backup folder does not exist, `backup` exits 1 with a message naming the folder and writes nothing.
- AC-3.3: The backup folder comes from `paths.backup_dir` in `config/pilot.yaml` (path overridable with `COTTONWOOD_CONFIG`), and `--to <dir>` overrides it for one run; when the database file does not exist, `backup` exits 1 naming it.
- AC-3.4: `.env.example` is committed, `.env` and the default backup folder are git-ignored, and the repository holds no email-sending credential settings (R-27, R-34).

### US-4 — Runbook for restore and deletion requests
As the developer, I want written restore and deletion-request procedures, so that a restore is rehearsed the same way every time and a deletion request never removes a suppression entry.

Acceptance criteria:
- AC-4.1: `docs/runbook.md` has a "Restore from backup" section whose steps copy the current database aside first, copy the chosen backup into place, check that it opens and contains the `suppression` table, run `cottonwood migrate`, and re-apply suppression entries added after the backup was taken.
- AC-4.2: `docs/runbook.md` has a "Deletion requests" section whose steps clear the person's contact fields and notes, mark the contact deleted, take a backup first, and state that the suppression entry is kept.
- AC-4.3: A test runs the restore section's commands against a scratch database and backup (using `sqlite3` from Python), and the restored file passes the section's own checks.

## Constraints & assumptions
- Follows `architecture.md` decisions 1, 2, 5, 9 and 10 and its table list; times are stored as UTC ISO-8601 text (R-32); money as decimal text.
- The baseline is `001_baseline.sql` (scaffold assumption), so the schema is `002_core.sql`, not `001_init.sql` as the architecture names it.
- Assumed (build question 1): the data-core / inbound-logging split above — data-core owns the schema, helpers, backup and the restore + deletion runbook sections; inbound-logging owns `log-inbound`, `review` and the inbound checklist + relay sections.
- Assumed (build question 2): phone normalization is hand-written for US/E.164 (default country +1) rather than the `phonenumbers` package.
- Assumed (build question 3): `config/pilot.yaml` is introduced now with only `paths.backup_dir` (default `data/backups`), read with PyYAML (architecture decision 5); later features add keys.
- Assumed (build question 4): `suppression` rejects UPDATE as well as DELETE; `activities` type is free text (validated in code by the commands that write it), so new activity types need no migration.
- Assumed (build question 5): the `tzdata` package is a dependency so America/Denver resolves on any machine.
- Assumed (build question 6): connections enable `PRAGMA foreign_keys = ON`; contacts are soft-deleted (`deleted_at`) with their fields cleared, per R-35.

## Success metrics
- The phase-2 exit criteria for the schema, triggers, backup and runbook sections all hold on a fresh checkout.
- Every later feature writes through these tables without a schema change for its own core columns.

## Open questions
- None blocking.
