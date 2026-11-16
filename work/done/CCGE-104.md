# CCGE-104 — set-eligibility command with source, identity and suppression checks

## Goal
Change a contact's eligibility only with a recorded basis: eligible needs a public professional source URL and an unambiguous identity and is refused for suppressed or deleted contacts.

## Inputs
Spec: `work/specs/prospect-review/spec.md` (AC-1.1, AC-1.2, AC-1.3)
Plan: `work/specs/prospect-review/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/eligibility.py: EligibilityError carrying every (field, rule) failure; set_eligibility(conn, contact_id, to, source_url, actor, now) in one transaction: load the contact (unknown id -> 'no contact N'); no-op when unchanged; for eligible check source-url required/url (http/https with host, reuse validate.is_http_url), contact suppressed (normalized email in suppression), deleted, identity (name and email present, no other not-deleted contact with the same email_norm); unknown on a suppressed address -> suppressed; update eligibility (and source_url for eligible); append eligibility_set with contact_id, lead_id NULL, payload {from, to, basis} (public-source-url or manual).
2. cli.py: set-eligibility CONTACT {eligible,ineligible,unknown} [--source-url] [--actor] [--db]; print 'contact N: eligibility FROM -> TO' or 'contact N: eligibility already TO'; refusals print one 'error: FIELD: RULE' line per failure and exit 1.
3. New tests: tests/test_set_eligibility.py.

## Acceptance Criteria
- [x] For a not-deleted contact 1 with a name and email, eligibility unknown, email_norm unique among not-deleted contacts and not suppressed, 'cottonwood set-eligibility 1 eligible --source-url https://acme.example/team' exits 0, prints 'contact 1: eligibility unknown -> eligible', stores eligibility eligible and source_url https://acme.example/team on contact 1, and writes exactly one new activity: type eligibility_set, contact_id 1, lead_id NULL, payload exactly {"from": "unknown", "to": "eligible", "basis": "public-source-url"}.
- [x] 'set-eligibility 1 eligible' without --source-url exits 1 with a stderr line 'error: source-url: required'; with --source-url ftp://acme.example/x it reports 'error: source-url: url'; in both cases contacts and activities are unchanged.
- [x] When contact 1's email_norm is in suppression, 'set-eligibility 1 eligible --source-url https://acme.example/team' exits 1 with 'error: contact: suppressed' and 'set-eligibility 1 unknown' exits 1 with 'error: contact: suppressed', while 'set-eligibility 1 ineligible' exits 0 and writes an eligibility_set activity whose payload basis is 'manual'.
- [x] 'set-eligibility 1 eligible --source-url https://acme.example/team' exits 1 with 'error: contact: deleted' for a contact with deleted_at set, and with 'error: contact: identity' for a contact with no name, for one with no email, and for one whose email_norm another not-deleted contact also has; a contact both suppressed and nameless gets both error lines.
- [x] 'set-eligibility 99 eligible --source-url https://acme.example/team' with no contact 99 exits 1 with stderr 'error: no contact 99'; setting contact 1 to the eligibility it already has exits 0, prints 'contact 1: eligibility already eligible' and writes no activity.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
