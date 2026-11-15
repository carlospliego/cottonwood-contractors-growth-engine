# CCGE-057 — Stage moves within R-14 and the R-16 qualification rule

## Goal
Let an event move the lead's stage only to an R-14 value for its type, record each move as a stage_change naming the event, and allow buyer_need_confirmed only with a stated need or procurement URL (R-14, R-15, R-16).

## Inputs
Spec: `work/specs/events-and-stages/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-3.1, AC-3.2, AC-3.3, AC-6.2)
Plan: `work/specs/events-and-stages/plan.md`

## Constraints
_None._

## Plan
1. In events.py add DIRECT_STAGES and RELATIONSHIP_STAGES (R-14 order) and STAGES_BY_LEAD_TYPE for inbound_inquiry, direct_candidate and relationship_prospect.
2. Extend RawEvent/Event with stage, need and procurement_url. validate_event: need/procurement_url only allowed with stage buyer_need_confirmed (else EventError); buyer_need_confirmed requires non-blank need or a procurement_url whose urlparse scheme is http/https with a netloc.
3. log_event: inside the transaction read the lead's type and stage; refuse a stage not in STAGES_BY_LEAD_TYPE[type] or equal to the current stage with a message listing the allowed stages; insert the event (payload adds need/procurement_url when given), UPDATE leads.stage, insert stage_change with payload {from, to, event_activity_id} and the event's occurred_at; return (event_id, stage_change_id, from_stage); rollback on any exception.
4. CLI: add --stage, --need, --procurement-url; success line appends 'stage <from> -> <to>'.
5. Add tests/test_events_stages.py (every stage per lead type with direct and relationship leads inserted by SQL, payload, refusals with unchanged stage and activity count, rollback via a trigger that raises on stage_change insert) and tests/test_events_qualify.py.

## Acceptance Criteria
- [x] For inbound lead 1 at stage candidate, `log-event 1 call --at "2026-11-16 09:30" --stage contacted_or_replied` exits 0, sets leads.stage to contacted_or_replied, and appends the call activity plus exactly one stage_change activity with the same occurred_at whose payload has from 'candidate', to 'contacted_or_replied' and event_activity_id equal to the call activity's id; stdout contains 'stage candidate -> contacted_or_replied'.
- [x] Every R-14 direct/inbound stage other than the current one is accepted for inbound_inquiry and direct_candidate leads, and every relationship stage other than the current one for relationship_prospect leads, in any order (buyer_need_confirmed given with --need).
- [x] A stage outside the lead type's list (introduced on an inbound lead, walkthrough on a relationship prospect, bogus) or equal to the current stage exits 1 with stderr listing that type's allowed stages, writes no activity and leaves leads.stage unchanged.
- [x] --stage buyer_need_confirmed with --need 'needs 4,000 sq ft office TI by March' exits 0 and stores payload.need with that text; with --procurement-url https://bids.example.gov/rfp/123 it exits 0 and stores payload.procurement_url.
- [x] --stage buyer_need_confirmed with neither --need nor --procurement-url, with whitespace-only --need, or with a procurement URL that is not absolute http(s) (e.g. 'bids.example.gov/rfp', 'ftp://x/y') exits 1, writes nothing and leaves the stage unchanged; --need or --procurement-url without --stage buyer_need_confirmed (no --stage, or --stage walkthrough) exits 1 and writes nothing.
- [x] When a temporary trigger makes the stage_change insert fail, log-event exits 1 with 'error:' on stderr and no traceback, and afterwards the lead has no new activities and its stage is unchanged.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-056
