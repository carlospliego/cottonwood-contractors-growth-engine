# cottonwood-contractors-growth-engine

<!-- A map, not a manual: keep this file under 100 lines. Put detail in docs/ and link it. -->

## What this is
cottonwood-contractors-growth-engine — one or two sentences: what it does and who it is for.

## Map
- Source: describe the top-level directories and what lives where.
- Docs: link architecture, testing, and runbook docs here as they appear.
- Work tracking: `work/todo.md` (index) and `work/tasks/` (one contract per task), managed by `/sir:task`.

## Commands
- No checks configured yet; add them to `.sir/config.yaml` under `checks:`.
- `sir` CLI calls, `git worktree add/remove`, `uv sync` and `git push` need the sandbox disabled (they write `.git/worktrees` or use the network).

## Rules
- Plan before building anything non-trivial: `/sir:plan` for features, `/sir:task add` for single changes.
- Every task has falsifiable acceptance criteria; it is done only when `/sir:verify` passes them.
- Never commit to `main` directly; `/sir:ship` opens the PR.
- Lessons that should change behavior go through `/sir:retro`, not ad-hoc notes here.
