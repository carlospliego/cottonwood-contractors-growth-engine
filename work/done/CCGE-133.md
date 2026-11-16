# CCGE-133 — log-reply: record replies; opt-out suppresses and bounce makes ineligible in the same command

## Goal
Record each reply by type, and for an opt-out add the contact's address to suppression, and for a bounce set the contact ineligible, in the same transaction, so no later send can reach them (R-23, R-24).

## Inputs
Spec: `work/specs/send-gate/spec.md` (AC-4.1, AC-4.2, AC-4.3, AC-5.1)
Plan: `work/specs/send-gate/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/gate.py: extract _insert_suppression(conn, email_norm, reason, source, now) -> existing row or None (no transaction) used by suppress.
2. cottonwood/send.py: REPLY_TYPES; ReplyResult with lines(); log_reply(conn, lead_id, reply_type, day, note, actor, now): unknown lead 'lead'; opt_out/bounce need the lead's contact with an email ('contact'); BEGIN IMMEDIATE: insert reply {type, received_on, note}; opt_out: _insert_suppression(email_norm, 'opt-out reply to lead L', 'log-reply', now) and insert suppressed {source: 'log-reply'} with contact_id; bounce: eligibility._apply(conn, contact_id, 'ineligible', None, actor, now).
3. cottonwood/cli.py: log-reply Command (lead, type choices REPLY_TYPES, --date, --note, --actor, --db) printing 'reply recorded: lead L TYPE (activity N)' and the side-effect line.
4. tests/test_log_reply.py.

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z, 'cottonwood log-reply 1 interested --date 2026-11-30 --note "wants a call"' exits 0, prints 'reply recorded: lead 1 interested (activity N)' and appends one reply activity with lead_id 1 and payload {type: interested, received_on: 2026-11-30, note: wants a call}; each of interested, not_now, not_relevant, referral, opt_out, bounce and other exits 0, and 'log-reply 1 maybe' exits 2.
- [x] 'cottonwood log-reply 1 opt_out' for a lead whose contact C has email Pat@Firm.example.com exits 0, prints 'suppressed: contact C' as a second line, stores a suppression row with email_norm pat@firm.example.com, reason 'opt-out reply to lead 1' and source 'log-reply', and appends a reply and a suppressed activity (contact_id C, payload without '@'); when the address is already suppressed the row is unchanged; afterwards prepare-send for lead 1 fails the suppression check.
- [x] 'cottonwood log-reply 1 bounce' for a lead whose contact C is eligible exits 0, prints 'contact C: eligibility eligible -> ineligible', sets contacts.eligibility to ineligible and appends a reply and an eligibility_set activity; 'log-reply 2 opt_out' and 'log-reply 2 bounce' for a lead without a contact email exit 1 with a stderr line starting 'error: contact:' and append nothing; 'log-reply 99 other' exits 1 with 'error: lead:'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-131
