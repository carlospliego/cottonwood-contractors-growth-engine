# CCGE-150 — research-prospects demand mode, and every researched prospect carries a reachable contact (phone or address allowed)

## Goal
The developer wants the research skill to pick the best current opportunity in Cottonwood's territory itself (`/research-prospects demand [COUNT]`), and to return only prospects someone can actually reach. Past runs returned records with a name but no email, phone or address, which are not useful. A contact must be allowed to be only a phone or a business postal address, stored and visible in review, so phone and mail leads are not lost.

## Inputs
.claude/skills/research-prospects/SKILL.md; cottonwood/schemas/research-record.schema.json; cottonwood/validate.py (CSV_COLUMNS, ProspectContact, _contact); cottonwood/prospects.py (_differences, _insert_contact); cottonwood/migrations/ (new 006_contact_address.sql); cottonwood/review.py (CANDIDATE_LEADING_COLUMNS, CandidateRow, candidate_rows, _candidate_section); docs/runbook.md 'Research run'; SPEC.md section 1 (territory, segments, capacity). Tests: tests/test_research_skill.py, tests/test_research_skill_scoping.py, tests/test_review_candidates.py, tests/test_migrate.py, tests/test_schema.py, tests/test_backup.py. The work is already done in the main working tree on 2026-11-18; this contract records and verifies it.

## Constraints
Keep the skill's allowed-tools unchanged (scoping test): territory and segments are written into the skill, not read from SPEC.md. The Reach column shows which routes exist, never their values. Never store or ask for a private individual's home address. Lead exports for prepare-outreach still carry no email or address. No change to eligibility rules (eligible still needs name and email). Synthetic test fixtures only; no network in tests.

## Plan
1. Skill v1.2.0: add a `demand [COUNT]` argument with a Demand mode section: a fixed pilot profile, a scan, a shortlist of 3-5 rated candidates (reachability counted twice, low reachability never wins, relationship prospects win close calls), a written brief, and a demand report out/research/YYYY-MM-DD-SLUG.demand.md.
2. Skill: add a contact-finding step (own site, NPI Registry, directories, the notice that produced the signal, broker listing); rules that every record has a contact with email, phone or business address, otherwise it is dropped, and no home addresses; the worked example's relationship record gets a phone and address contact; update the after-run version to 1.2.0.
3. Schema: contact anyOf name/email/phone/address; add contact.address as a non-blank string.
4. validate.py: ProspectContact.address, CSV column contact_address; prospects.py stores the address and compares it on re-import.
5. Migration 006_contact_address.sql adds a nullable contacts.address column.
6. review.py: a Reach column after Contact listing the email/phone/address routes on file, or 'none' when there is no contact or it is deleted.
7. Runbook research step mentions demand mode and the demand report.
8. Tests: tests/test_prospects_contact_address.py, a reach test in tests/test_review_candidates.py, and schema version 6 in existing tests; run all checks.

## Acceptance Criteria
- [x] A pytest test imports a JSON record whose contact has only `address` (plus source_url) and asserts the stored contacts row has that address and NULL name and email; another imports a phone-only contact and asserts phone_e164 is +18015550100.
- [x] A pytest test asserts `prospects-import --check` rejects a contact with only `role`, and a contact whose `address` is blank, each with a rejection line naming `contact` and the summary `check: 0 valid, 1 rejected`.
- [x] A pytest test imports a CSV row with a `contact_address` column and asserts the stored address; a second test re-imports a matched record with a different address and asserts the output names `contact.address` as a difference.
- [x] `cottonwood migrate` on a fresh database reaches version 6 and contacts has an `address` column; a pytest test asserts the review queue's fourth column is `Reach` and shows 'email, phone, address', 'phone', 'address' and 'none' (deleted contact) for the matching contact rows.
- [x] `.claude/skills/research-prospects/SKILL.md` has version 1.2.0, documents the `demand` argument and the `.demand.md` report, requires a contact with email, phone or address on every record, forbids private home addresses, and keeps the same allowed-tools; `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-18.

## Depends on
_None._
