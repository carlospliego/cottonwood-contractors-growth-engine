# CCGE-089 — prospects-import command: create leads, record rejections, suppression, referrals and test labels

## Goal
Import validated research records as new organizations, contacts, leads and evidence, one savepoint per record, with imported and import_rejected activities the weekly report already counts.

## Inputs
Spec: `work/specs/prospect-import/spec.md` (AC-1.1, AC-1.2, AC-1.4, AC-2.1, AC-2.4, AC-4.1, AC-4.2, AC-4.3, AC-4.4)
Plan: `work/specs/prospect-import/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/migrations/004_prospects.sql: leads.verified_facts TEXT, evidence.observation TEXT; update the tests that pin the schema version to 4.
2. cottonwood/prospects.py: ImportResult; import_records(conn, file_name, records, actor) where records are ProspectRecord or Rejection in file order; per record a SAVEPOINT: referrer check (existing relationship_prospect lead, else Rejection referred_by: referrer), organization insert (name_norm, domain_norm), optional contact insert (eligibility ineligible when email_norm is in suppression, else unknown), lead insert at stage researched, evidence inserts, one imported activity {file, record, record_id, created, new_evidence}; each Rejection writes one import_rejected activity {file, record, record_id, field, rule}.
3. cottonwood/cli.py: prospects-import FILE [--db] [--actor]; missing/unmigrated database as other commands; FileError -> exit 1 'error: ...' with nothing written; per-record stdout lines, rejected lines on stderr, summary 'imported I, matched M, rejected R'; exit 1 when R > 0.
4. tests/test_prospects_import.py.

## Acceptance Criteria
- [x] Importing a JSON file of one valid direct_candidate and one valid relationship_prospect record exits 0, stores two leads of those types at stage researched with their organizations, one evidence row each and verified_facts as a JSON array, writes one counted imported activity per lead, and prints 'imported 2, matched 0, rejected 0' as the last stdout line; importing the same two records as a CSV into a fresh database stores leads, organizations, contacts and evidence with equal values apart from ids.
- [x] For a .txt file, a missing file, invalid JSON, a JSON object top level and a CSV without the evidence_url column, prospects-import exits 1 with stderr starting 'error:' and containing the file path, and the row counts of organizations, contacts, leads, evidence and activities are unchanged.
- [x] In a three-record file whose record 2 has no evidence[0].url, stderr contains 'rejected record 2: evidence[0].url: required', records 1 and 3 become leads, no organization, contact, lead or evidence row comes from record 2, exactly one counted import_rejected activity is written whose payload has keys file, record, record_id, field and rule and contains none of record 2's excerpt, contact name or email text, stdout ends 'imported 2, matched 0, rejected 1', and the exit code is 1.
- [x] A record whose contact email normalizes to an address in suppression stores the contact with eligibility ineligible, every other imported contact has eligibility unknown, and no contact row has eligibility eligible after the import.
- [x] referred_by naming an existing relationship_prospect lead id is stored on the new lead; referred_by naming a lead id that does not exist, or a direct_candidate lead, rejects the record with 'referred_by: referrer' and writes nothing from it.
- [x] After importing one non-test direct record, one non-test relationship record, one record with is_test true (stored is_test 1) and one rejected record, cottonwood report for a period containing today shows 'Researched direct candidates: 1', 'Researched partner firms: 1' and 'Data-quality failures: 1'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-088

## Tests to change
- `tests/test_backup.py`
- `tests/test_inbound.py`
- `tests/test_migrate.py`
- `tests/test_runbook_restore.py`
- `tests/test_schema.py`
