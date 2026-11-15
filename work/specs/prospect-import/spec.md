# Prospect Import — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
The developer will research direct candidates and relationship prospects (by hand or with the research skill) and needs them in the database as leads with their evidence, so they can be hand-reviewed, queued and later contacted. Today there is no way to load them: only inbound inquiries can be logged. Research output is untrusted, so the import must refuse anything that is not evidence-backed, say exactly what was wrong, never guess, and never create duplicates when the same research is imported twice (docs/cottonwood-growth-engine.md R-5–R-7, R-9, R-12, R-24, R-25).

## Goals / non-goals
- Goal: `cottonwood prospects-import FILE` loads JSON or CSV research records as `direct_candidate` / `relationship_prospect` leads with organization, optional contact and evidence.
- Goal: every invalid record is rejected by name (record, field, rule), nothing of it is written, valid records in the same file still import, and each rejection counts as a data-quality failure in the report.
- Goal: re-importing creates no duplicates; a matched record only gains new evidence and the import prints each differing field.
- Goal: suppressed addresses import as `ineligible`; money values carry a basis; referrals link to a partner lead.
- Non-goal: `set-eligibility`, `mark-reviewed`, the candidate queues in `review` and evidence-age display (feature `prospect-review`).
- Non-goal: the `research-prospects` skill and `record-run` (feature `research-skill`); this feature ships the record schema the skill will write against.
- Non-goal: repairing or guessing invalid input (R-25), fetching any URL, or changing a stored value from an import.

## User stories
### US-1 — Import research records from JSON or CSV
As the developer, I want to import a file of research records, so that evidence-backed prospects become leads I can review.

Acceptance criteria:
- AC-1.1: A JSON file holding an array of two valid records — one `direct_candidate`, one `relationship_prospect`, each with `organization.name`, `verified_facts`, `hypothesis` and one evidence item with `url`, `observed_at` and `excerpt` — makes `cottonwood prospects-import FILE` exit 0 and store two leads of those types at stage `researched`, each with its organization, one evidence row and one counted `imported` activity; stdout ends with the line `imported 2, matched 0, rejected 0`.
- AC-1.2: A CSV file with a header row and one row per record (one evidence item per row; `verified_facts` cells separated by newlines) imports leads, organizations, contacts and evidence with the same stored values as the equivalent JSON records.
- AC-1.3: `cottonwood/schemas/research-record.schema.json` is a JSON Schema (draft 2020-12) that passes `Draft202012Validator.check_schema`; it requires `type`, `organization.name`, `verified_facts`, `hypothesis` and at least one evidence item with `url`, `observed_at` and one of `excerpt` or `observation`; every record is validated against it before anything of the record is written.
- AC-1.4: A file whose extension is not `.json` or `.csv`, a missing or unreadable file, invalid JSON, a JSON top level that is not an array, or a CSV header missing a required column makes the command exit 1 with stderr starting `error:` and naming the file, and writes no row in any table.

### US-2 — Reject invalid records by record, field and rule
As the developer, I want each invalid record refused with the exact reason, so that I can correct the research instead of finding bad data later.

Acceptance criteria:
- AC-2.1: In a three-record file whose record 2 lacks `evidence[0].url`, stderr has the line `rejected record 2: evidence[0].url: required` (with ` (RECORD_ID)` after the number when the record has a `record_id`); records 1 and 3 are imported; no organization, contact, lead or evidence row comes from record 2; one counted `import_rejected` activity is written; stdout ends `imported 2, matched 0, rejected 1`; the command exits 1.
- AC-2.2: Each of these rejects its record with the field and rule shown: `type` not one of the two record types (`type: enum`); an empty evidence list (`evidence: minItems`); an evidence URL that is not http(s) with a host (`evidence[0].url: url`); `observed_at` not a real YYYY-MM-DD date (`evidence[0].observed_at: date`) or later than today in America/Denver (`evidence[0].observed_at: not-future`); a contact email that does not normalize (`contact.email: email`); a contact phone that does not normalize to E.164 (`contact.phone: phone`); missing `verified_facts` or `hypothesis` (`verified_facts: required`, `hypothesis: required`).
- AC-2.3: A `value` of amount `250000.00` with basis `founder-estimated` stores `value_amount` `250000.00` and `value_basis` `founder-estimated`; an amount without a basis is rejected `value.basis: required`; a basis outside `buyer-stated`, `founder-estimated`, `unverified` is rejected `value.basis: enum`; an amount that is not an exact non-negative plain decimal (`2.5e5`, `-1`, `abc`, `1,000`) is rejected `value.amount: decimal` (R-9).
- AC-2.4: The `import_rejected` payload holds the file name, record number, record_id, field and rule, and none of the record's excerpt, observation, name, email or phone text; `cottonwood report` for a period containing it shows `Data-quality failures: 1`.

### US-3 — Re-import without duplicates
As the developer, I want importing the same or overlapping research again to be safe, so that I can re-run imports without cleaning up duplicates.

Acceptance criteria:
- AC-3.1: Importing the same valid file a second time exits 0, prints `imported 0, matched 2, rejected 0`, and leaves the row counts of organizations, contacts, leads, evidence and activities unchanged.
- AC-3.2: A record whose `organization.domain` is `WWW.Acme.com` matches a stored organization whose `domain_norm` is `acme.com` even when the names differ; a record without a domain matches a stored organization with the same normalized name; a record whose domain no stored organization has creates a new organization.
- AC-3.3: A contact matches a stored, not-deleted contact on normalized email, or, when the record has no email, on normalized name within the same organization; a lead matches a stored lead with the same organization, type and property location (trimmed and compared case-insensitively; both empty also match).
- AC-3.4: A matched record carrying one evidence item not already stored for that lead (by URL, observed date and excerpt or observation) adds exactly that evidence row and one `imported` activity, changes no stored lead, organization or contact value, and prints `record N: FIELD differs: stored 'X', incoming 'Y' (kept stored)` for each field whose incoming non-empty value differs from the stored one.
- AC-3.5: When two records in one file describe the same lead, the first is reported as created and the second as matched; the file's summary counts them as `imported 1, matched 1`.

### US-4 — Suppression, eligibility, test labels and referrals
As the developer, I want imports to respect suppression and record referrals and test labels, so that no suppressed person becomes contactable and the report counts the right leads.

Acceptance criteria:
- AC-4.1: A new contact whose normalized email is in `suppression` is stored with eligibility `ineligible`; every other new contact is stored `unknown`; an import never stores `eligible` (R-8, R-24).
- AC-4.2: `referred_by` naming an existing `relationship_prospect` lead id is stored on the new lead; naming a lead id that does not exist, or a lead of another type, rejects the record with `referred_by: referrer` (R-12).
- AC-4.3: `is_test: true` stores `is_test` 1 on the lead, and `cottonwood report` for the import's period counts such a lead in neither `Researched direct candidates` nor `Researched partner firms`.
- AC-4.4: After importing one non-test direct record and one non-test relationship record, `cottonwood report` for that period shows `Researched direct candidates: 1` and `Researched partner firms: 1`.

## Constraints & assumptions
- Validation is jsonschema against a schema file shipped inside the package (architecture.md decision 4), plus Python checks the schema cannot express (dates not in the future, URL host, email/phone normalization, exact decimals, the referrer lead). Invalid records are never repaired (R-25).
- New leads enter at stage `researched` (both lead types have it, R-14); the `imported` activity records it, with no separate `stage_change`.
- Activity payloads hold no personal data (names, emails, phones, excerpts), because activities are append-only and a deletion request must be able to remove contact data (R-35).
- An identical re-import writes no rows at all, including activities, so a re-run in a later week does not count the leads as researched again.
- A matched record never changes stored values (R-7), including a matched contact's eligibility; suppression is enforced again by `set-eligibility` and `prepare-send` (R-24).
- CSV carries one evidence item per row; more evidence for the same lead comes from more rows, which match the lead (US-3) and add their evidence.
- The command exits 1 when any record is rejected, after importing the valid ones, so a script notices the failure; it exits 0 only when nothing was rejected.

## Success metrics
- The phase-4 exit criterion holds: `prospects-import` accepts valid fixture records, rejects invalid ones naming the record, field and rule, and re-import creates no duplicates (work/initiatives/cottonwood-growth-engine/roadmap.md, phase 4).

## Open questions
- [Founder, before first send] The maximum evidence age (docs/cottonwood-growth-engine.md:136); import stores observed dates and leaves age checks to `review` and `prepare-send`.
