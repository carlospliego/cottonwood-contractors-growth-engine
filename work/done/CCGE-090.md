# CCGE-090 — Re-import matching: no duplicates, new evidence only, differing fields printed

## Goal
Make re-importing the same or overlapping research create no duplicate organizations, contacts, leads or evidence, add only new evidence, keep stored values and print what differs (R-7).

## Inputs
Spec: `work/specs/prospect-import/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5)
Plan: `work/specs/prospect-import/plan.md`

## Constraints
_None._

## Plan
1. prospects.py: organization match by domain_norm when the record has a domain, else by name_norm; contact match on email_norm among not-deleted contacts, else normalized name within the organization; lead match on organization_id, type and property location (trimmed, casefolded, both empty match); evidence dedupe on lead, url, observed_at and excerpt/observation.
2. Matched rows are never updated; build the differing-field list (plan.md Diff fields) and print 'record N: FIELD differs: stored 'X', incoming 'Y' (kept stored)'.
3. A matched lead that gains evidence gets one imported activity (created false, new_evidence K); a fully matched record with nothing new writes no row and prints 'record N: matched lead L'.
4. tests/test_prospects_reimport.py.

## Acceptance Criteria
- [x] Importing the same valid two-record file twice: the second run exits 0, prints 'imported 0, matched 2, rejected 0', and the row counts of organizations, contacts, leads, evidence and activities are the same after it as before it.
- [x] With a stored organization whose domain_norm is acme.com, a record with organization.domain 'WWW.Acme.com' and a different name matches it; a record with no domain matches a stored organization with the same normalized name; a record whose domain no stored organization has creates a new organization even when its name matches a stored one.
- [x] A record matches a stored not-deleted contact on normalized email, or without an email on normalized name within the same organization, and does not match a contact with deleted_at set; a record matches a stored lead with the same organization and type when property locations are ' 12 Main St ' and '12 main st', or both empty, and creates a new lead when they differ.
- [x] Re-importing a matched record with one additional evidence item and a different organization.category adds exactly one evidence row and one imported activity, leaves the stored organization, contact and lead values unchanged, and prints a line containing 'organization.category differs' with the stored and incoming values and 'kept stored'.
- [x] A file with two records describing the same lead reports the first as created and the second as matched, and ends 'imported 1, matched 1, rejected 0'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-089
