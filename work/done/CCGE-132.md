# CCGE-132 — log-outreach: record a send and flag any send that bypassed the gate

## Goal
Record each send the founder performed with its prepared-draft reference, source, message digest, sender, date and provider ID, and record and report a gate violation when the send had no matching prepared draft, a different message, a different recipient, or a recipient suppressed since preparation (R-22).

## Inputs
Spec: `work/specs/send-gate/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-5.1)
Plan: `work/specs/send-gate/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/send.py: OutreachResult(sent_id, violation_id, reasons) with line(); log_outreach(conn, lead_id, prepared, recipient, source_url, message, sender, day, provider_message_id, actor, now): refuse (SendError) blank sender, non-http(s) source URL, unreadable message, unknown lead, bad recipient address; reasons: prepared missing or not a draft_prepared of this lead ('no prepared draft'), message sha256 != prepared sha256 ('message differs from the prepared draft'), normalized recipient != prepared contact's email_norm ('recipient differs from the prepared contact'), recipient in suppression with added_at after the prepared activity's recorded_at ('recipient suppressed since preparation'). One transaction: insert sent (lead_id, contact_id = prepared contact or lead contact) with payload incl. recipient_matches, then gate_violation {sent_activity_id, reasons} if any.
2. cottonwood/cli.py: log-outreach Command (lead, --prepared int, --recipient, --source-url, --message, --sender, --date default today, --provider-message-id, --actor, --db); prints 'send recorded: lead L (activity N)' then one 'gate violation: REASON' stderr line per reason, exit 1 when any.
3. tests/test_log_outreach.py reusing a prepared-draft fixture.

## Acceptance Criteria
- [x] After a successful prepare-send recorded as activity P for lead 1, 'cottonwood log-outreach 1 --prepared P --recipient CONTACT_EMAIL --source-url https://firm.example.com/team --message SENDABLE --sender Founder --date 2026-11-30 --provider-message-id abc123' exits 0, prints 'send recorded: lead 1 (activity N)', appends exactly one new activity of type sent with lead_id 1 and the contact's id whose payload has prepared P, source_url, message_sha256 equal to the sendable file's sha256, sender Founder, sent_on 2026-11-30, provider_message_id abc123 and recipient_matches true, and no payload value contains '@'.
- [x] Each of these appends a sent activity and a gate_violation activity whose payload has sent_activity_id equal to the sent id and reasons [REASON], prints a stderr line 'gate violation: REASON' and exits 1: no --prepared ('no prepared draft'); --prepared naming a prepare_refused activity or another lead's draft_prepared ('no prepared draft'); --message a file with different bytes ('message differs from the prepared draft'); --recipient another address ('recipient differs from the prepared contact'); the contact's address suppressed with cottonwood suppress after the prepare-send ('recipient suppressed since preparation').
- [x] Each of these exits 1 with a stderr line starting 'error: FIELD:' and appends no activity: blank --sender (sender), --source-url ftp://x (source_url), a missing --message file (message), --date 2026-12-01 and --date 30/11/2026 (date), --recipient not-an-email (recipient), lead 99 (lead).
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-131
