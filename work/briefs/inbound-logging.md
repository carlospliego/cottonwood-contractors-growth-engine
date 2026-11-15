# Brief: Inbound Logging

Written by `sir plan briefs cottonwood-growth-engine` from the roadmap. Edit it freely; re-running never overwrites it.

## Why
Phase 2 of work/initiatives/cottonwood-growth-engine/roadmap.md: Durable data core and inbound capture (software side of Gate 0)

## Scope
The part of phase 2 that `inbound-logging` delivers. Phase exit criteria: All 7 tables migrate on a fresh database; UPDATE/DELETE on `activities` and DELETE on `suppression` are rejected; `backup` writes a consistent timestamped copy, and the runbook restore procedure restores it; a labeled test form inquiry and test phone inquiry logged with `log-inbound` appear labeled in `review` and are excluded from counts; the duplicate check fires on a same-day match; `docs/runbook.md` has the inbound checklist, relay, restore and deletion-request sections (R-1–R-4, R-31 for review, R-32–R-35)
Other features in this phase, built separately: `data-core`.

## Sources
- docs/cottonwood-growth-engine.md
- work/initiatives/cottonwood-growth-engine/project.md: outcomes and scope
- work/initiatives/cottonwood-growth-engine/architecture.md: follow its decisions
- work/initiatives/cottonwood-growth-engine/verification.md: how outcomes are measured

## Depends on
Built and merged first: `scaffold`.
