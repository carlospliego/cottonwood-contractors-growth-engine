# CCGE-153 — Spec R-26: say token count and cost are recorded when a figure is available

## Goal
CCGE-152 made record-run's --tokens and --cost optional for subscription plans where /cost shows no dollar figure (stored as unknown, never 0). The spec's R-26 in docs/cottonwood-growth-engine.md still says every run is recorded with a token count and cost from a named source, so the spec and the code disagree.

## Inputs
docs/cottonwood-growth-engine.md line 60 (R-26); seen while working CCGE-152 (cottonwood/runs.py, docs/runbook.md Research run step 7).

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] The R-26 line in docs/cottonwood-growth-engine.md says token count and cost are recorded when a figure is available and are stored as unknown (not 0) otherwise, and still names the two cost sources and the estimated mark.

## Depends on
_None._
