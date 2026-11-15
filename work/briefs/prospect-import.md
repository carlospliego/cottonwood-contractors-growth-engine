# Brief: Prospect Import

Written by `sir plan briefs cottonwood-growth-engine` from the roadmap. Edit it freely; re-running never overwrites it.

## Why
Phase 4 of work/initiatives/cottonwood-growth-engine/roadmap.md: Evidence-backed prospects (software ready for Gate 1)

## Scope
The part of phase 4 that `prospect-import` delivers. Phase exit criteria: `prospects-import` accepts valid fixture records, rejects invalid ones naming the record, field and rule, and re-import creates no duplicates; `set-eligibility` refuses without a source or for suppressed addresses; `mark-reviewed` counts feed the report; `review` shows separate candidate queues with checklist, evidence age and the stated order; the `research-prospects` skill produces a file that validates and imports, and its run is recorded with cost and source (R-5–R-13, R-25–R-27)
Other features in this phase, built separately: `prospect-review`, `research-skill`.

## Sources
- docs/cottonwood-growth-engine.md
- work/initiatives/cottonwood-growth-engine/project.md: outcomes and scope
- work/initiatives/cottonwood-growth-engine/architecture.md: follow its decisions
- work/initiatives/cottonwood-growth-engine/verification.md: how outcomes are measured

## Depends on
Built and merged first: `events-and-stages`, `weekly-report`.
