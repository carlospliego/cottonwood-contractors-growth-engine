# CCGE-060 — Backdated stage changes and the latest-effective-stage rule disagree

## Goal
Make leads.stage and the latest effective stage change (ordered by occurred_at, id) agree, so a correction never discards a stage set by a backdated event (found by the CCGE-058 AC3 refuter).

## Inputs
cottonwood/events.py log_event stage update and log_correction latest-effective query (ORDER BY a.occurred_at DESC, a.id DESC),work/specs/events-and-stages/plan.md:55

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] On lead 1, after `log-event 1 call --at "2026-11-16 09:45" --stage contacted_or_replied` then `log-event 1 walkthrough --at "2026-11-16 09:30" --stage walkthrough`, either the second command exits 1 and writes nothing, or a later `log-event 1 correction --voids CALL_ID` (CALL_ID being the call's activity id) leaves leads.stage equal to the stage of the latest remaining effective stage change; a test in tests/ asserts whichever behavior is chosen.

All criteria verified 2026-11-20.

## Depends on
_None._
