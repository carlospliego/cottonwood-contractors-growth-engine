# Brief: Scaffold

Written by `sir plan briefs cottonwood-growth-engine` from the roadmap. Edit it freely; re-running never overwrites it.

## Why
Phase 1 of work/initiatives/cottonwood-growth-engine/roadmap.md: Runnable skeleton that every later build is checked with

## Scope
The part of phase 1 that `scaffold` delivers. Phase exit criteria: `uv run cottonwood --help` lists the CLI; `pytest`, `ruff check`, `ruff format --check` and `mypy` run from the command line and pass on the skeleton; `cottonwood migrate` creates an empty versioned SQLite file; `/sir:init` re-run picks up the check commands

## Sources
- docs/cottonwood-growth-engine.md
- work/initiatives/cottonwood-growth-engine/project.md: outcomes and scope
- work/initiatives/cottonwood-growth-engine/architecture.md: follow its decisions
- work/initiatives/cottonwood-growth-engine/verification.md: how outcomes are measured

## Depends on
Nothing: this can be built first.
