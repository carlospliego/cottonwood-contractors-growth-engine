# Brief: Events And Stages

Written by `sir plan briefs cottonwood-growth-engine` from the roadmap. Edit it freely; re-running never overwrites it.

## Why
Phase 3 of work/initiatives/cottonwood-growth-engine/roadmap.md: Events, stages and an honest report

## Scope
The part of phase 3 that `events-and-stages` delivers. Phase exit criteria: `log-event` records every R-15 type and enforces R-14 stages and the R-16 qualification rule; corrections void activities and void activities drop out of counts; `log-time` and `log-cost` record hours and spend; `report --period 7d` and `--period 30d` write Markdown with every R-28 metric, zeros printed and the KPI shown as `n/a` at 0 hours, observed apart from estimated (R-14–R-17, R-28–R-31)
Other features in this phase, built separately: `weekly-report`.

## Sources
- docs/cottonwood-growth-engine.md
- work/initiatives/cottonwood-growth-engine/project.md: outcomes and scope
- work/initiatives/cottonwood-growth-engine/architecture.md: follow its decisions
- work/initiatives/cottonwood-growth-engine/verification.md: how outcomes are measured

## Depends on
Built and merged first: `data-core`, `inbound-logging`.
