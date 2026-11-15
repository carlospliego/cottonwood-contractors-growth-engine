# Brief: Send Gate

Written by `sir plan briefs cottonwood-growth-engine` from the roadmap. Edit it freely; re-running never overwrites it.

## Why
Phase 5 of work/initiatives/cottonwood-growth-engine/roadmap.md: Gated outreach loop (software ready for Gate 2)

## Scope
The part of phase 5 that `send-gate` delivers. Phase exit criteria: `approve` refuses without a written-approval reference; claims become `verified` only through a claim approval; `prepare-send` writes a sendable draft only when every R-21 check passes and names each failed check otherwise; `log-outreach` records a send and flags a bypass as a gate violation; `log-reply` opt-out suppresses and bounce makes ineligible in the same command; `suppress` works without a lead; the `prepare-outreach` skill outputs a draft, a claims list and a brief, and skips suppressed contacts (R-18–R-24)
Other features in this phase, built separately: `approvals-and-claims`, `outreach-skill`.

## Sources
- docs/cottonwood-growth-engine.md
- work/initiatives/cottonwood-growth-engine/project.md: outcomes and scope
- work/initiatives/cottonwood-growth-engine/architecture.md: follow its decisions
- work/initiatives/cottonwood-growth-engine/verification.md: how outcomes are measured

## Depends on
Built and merged first: `prospect-import`, `prospect-review`, `research-skill`.
