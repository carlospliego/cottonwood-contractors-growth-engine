# CCGE-118 — approve command: founder approvals of a lead, draft, audience or offer with a written-approval reference

## Goal
Record each founder approval with approver, approval date, scope, the item approved and a reference to the founder's written approval as an append-only approval activity, refusing without the reference; a draft approval names its lead and the draft's SHA-256 (R-18).

## Inputs
Spec: `work/specs/approvals-and-claims/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-4.1)
Plan: `work/specs/approvals-and-claims/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/gate.py: GateError(field, message) with str 'FIELD: MESSAGE'; SCOPES ('lead','draft','claim','audience','offer'); Approval frozen dataclass (activity_id, scope, item, approver, lead_id, approved_on) with line(); approve(conn, scope, item, approver, reference, day, lead_id, actor, now) that strips and checks approver/reference/actor, resolves the item per scope (lead: integer id that exists; draft: --lead required and existing, the path must be an existing file, sha256 of its bytes; audience/offer: non-blank text, optional existing --lead), and appends one 'approval' activity with events._insert_activity in a BEGIN IMMEDIATE transaction (occurred_at events._day_start(day), recorded_at now). The 'claim' scope raises GateError('scope', 'claim approvals arrive with the claims file') until T-02.
2. cottonwood/cli.py: approve Command: positional scope (choices SCOPES) and item, --approver (required), --reference (required argparse-wise but blank refused by gate), --lead int, --date (events._parse_entry_date, default events.denver_today(); bad -> 'error: date: ...'), --actor, --db; refusals 'error: FIELD: MESSAGE' exit 1.
3. tests/test_approve.py with utc_now pinned to 2026-12-01T00:00:00Z: printed lines, stored payloads (sha256 computed in the test with hashlib), audience/offer with and without --lead, every refusal with no activity appended, unknown scope exit 2.

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z and lead 1 stored, 'cottonwood approve lead 1 --approver Founder --reference "email 2026-11-29 Re: first prospects"' exits 0, prints 'approval 1 recorded: lead 1 by Founder', and appends one 'approval' activity with lead_id 1 whose payload has scope 'lead', item '1', approver 'Founder', reference 'email 2026-11-29 Re: first prospects' and approved_on '2026-11-30'; the same command with '--date 2026-11-29' records approved_on '2026-11-29'.
- [x] 'cottonwood approve draft DRAFT --lead 1 --approver Founder --reference "email 2026-11-30 Re: draft 1"' for an existing file DRAFT exits 0, prints 'approval N recorded: draft DRAFT for lead 1 by Founder' (N the activity id), and stores scope 'draft', item equal to the DRAFT argument, lead_id 1 and a payload 'sha256' equal to hashlib.sha256 of the file's bytes as hex.
- [x] 'approve audience "Salt Lake County property managers"' and 'approve offer "free walkthrough"' with --approver and --reference exit 0 and store scope 'audience' and 'offer' with that text as item and lead_id NULL; with '--lead 1' the activity has lead_id 1.
- [x] Each of these exits 1, prints one stderr line starting with the given prefix, and appends no activity: blank --reference ('error: reference:'); blank --approver ('error: approver:'); 'approve lead 99' with no lead 99 and 'approve lead abc' ('error: lead:'); 'approve draft' without --lead ('error: lead:'); 'approve draft' naming a missing file ('error: draft:'); a blank audience or offer item ('error: item:'); '--date 2026-12-01' and '--date 30/11/2026' ('error: date:'); 'approve offer x --lead 99' ('error: lead:'). 'approve vendor x ...' exits 2.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.
- [x] The changes to existing test `tests/test_no_send_credentials.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the repo scan fails on main because sir task contracts and specs under work/ quote the sample credential strings as criterion text; exempt only the work/ planning records so this task's pytest criterion can pass).

All criteria verified 2026-11-15.

## Depends on
_None._
