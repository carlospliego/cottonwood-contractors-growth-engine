# CCGE-058 — Corrections void events and void activities drop out of counts

## Goal
Void a mistaken event with an appended correction, revert the stage it caused when that change is the latest, and define the one counted-activity rule the report reuses (R-17).

## Inputs
Spec: `work/specs/events-and-stages/spec.md` (AC-4.1, AC-4.2, AC-4.3, AC-4.4, AC-4.5),Plan: `work/specs/events-and-stages/plan.md`

## Constraints
The correction and any stage-revert stage_change both carry the correction's --at. A correction whose --at is earlier than the voided activity's occurred_at is refused with exit 1 and field 'at' (build assumption 15).,'correction' is not added to EVENT_TYPES. The CLI accepts EVENT_TYPES + ('correction',). tests/test_events.py::test_unknown_type_is_a_usage_error drops 'correction' from its bad-type list via sir task allow-test, because correction becomes a valid type.

## Plan
In events.py add COUNTED_ACTIVITIES_SQL (the plan's fragment over alias a) and counted_activities(conn, type=None) returning activity rows ordered by occurred_at, id.,Add log_correction(conn, lead_id, voids_id, at, note, actor): in one transaction refuse a missing target, another lead's activity, a non-R-15 target, or an already-voided target; find the effective stage_change whose event_activity_id is the target; if one exists it must be the lead's latest effective stage change (occurred_at, id) or refuse naming the later one; insert the correction (voids_activity_id, payload {note?}); if reverting, UPDATE leads.stage to its from and insert stage_change {from: current, to: from, event_activity_id: correction id}; rollback on error.,CLI: type 'correction' accepted by log-event with --voids (required for correction, refused for other types) and --at; --stage/--need/--procurement-url with correction exit 1; success line names the voided activity and any stage revert.,Add tests/test_events_corrections.py.

## Acceptance Criteria
- [x] With E an event activity id of lead 1, `log-event 1 correction --voids E --at "2026-11-16 10:00"` exits 0 and appends exactly one correction activity for the lead whose voids_activity_id is that id; the voided activity row is identical before and after.
- [x] events.counted_activities(conn) excludes the voided event, the correction, and any stage_change whose event_activity_id is the voided event, and still includes the lead's other non-void events.
- [x] Voiding the event behind the lead's latest effective stage change sets leads.stage back to that change's from stage and appends a stage_change whose event_activity_id is the correction's id; when a later effective stage change exists, the correction exits 1 with stderr naming the later stage change's activity id and writes nothing.
- [x] A correction exits 1 and writes nothing when --voids is missing, the activity does not exist, belongs to another lead, is a stage_change, correction or inquiry_logged activity, is already void, or when --stage is given; --voids on a non-correction type exits 1.
- [x] events.counted_activities(conn) returns no activity whose lead has is_test 1.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.
- [x] The changes to existing test `tests/test_events.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: test_unknown_type_is_a_usage_error lists 'correction' as an invalid type (exit 2). The contract makes correction a valid log-event type (R-17 'log-event LEAD correction --voids ACTIVITY'), so 'correction' leaves that bad-type list; bogus, stage_change and Call stay. Correction refusals are covered in tests/test_events_corrections.py).

All criteria verified 2026-11-15.

## Depends on
CCGE-057
