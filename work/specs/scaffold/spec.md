# Scaffold — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
The repository has no application code (`work/initiatives/cottonwood-growth-engine/architecture.md:6`) and every sir check in `.sir/config.yaml:11-16` is `null`. Every later build of the Cottonwood Growth Engine is verified with test, lint, format and typecheck commands, so until a runnable Python skeleton exists no feature can be built or checked. It is solved when the skeleton installs with `uv`, its CLI runs, the four checks pass from the command line, and `cottonwood migrate` creates a versioned SQLite file.

## Goals / non-goals
- Goal: a `cottonwood` Python package with one CLI entry point, following the layout and decisions in `architecture.md` (argparse, stdlib `sqlite3`, plain SQL migrations applied with `PRAGMA user_version`, uv + pytest + ruff + mypy).
- Goal: `pytest`, `ruff check`, `ruff format --check` and `mypy` all run through `uv run` and pass on the skeleton, so `/sir:init` can pick them up.
- Goal: `cottonwood migrate` creates a SQLite file with no application tables and a version number, using a migrations runner later features extend by adding SQL files.
- Non-goal: any of the 7 tables, normalization, validation, config files (`config/*.yaml`), skills or any command other than `migrate` (later features).
- Non-goal: editing `.sir/config.yaml` checks by hand; the `/sir:init` re-run after this feature merges does that.

## User stories
### US-1 — Installable package with a CLI
As the developer, I want `uv run cottonwood --help` to work in a fresh checkout, so that every later feature has a CLI to add subcommands to.

Acceptance criteria:
- AC-1.1: `uv run cottonwood --help` exits 0 and its output contains the program name `cottonwood` and the subcommand `migrate`.
- AC-1.2: `uv run cottonwood` with no subcommand, and `uv run cottonwood not-a-command`, each exit with code 2 (usage error, per the architecture's exit codes).
- AC-1.3: `cottonwood.cli.main(argv)` is callable from tests with an argument list and returns the exit code as an int instead of calling `sys.exit` itself.

### US-2 — Checks that run from the command line
As the developer (and sir), I want test, lint, format and typecheck commands that run from the command line and pass on the skeleton, so that every later build is checked with them.

Acceptance criteria:
- AC-2.1: `uv run pytest` exits 0 and runs at least one test for the CLI and at least one for migrations.
- AC-2.2: `uv run ruff check` exits 0.
- AC-2.3: `uv run ruff format --check` exits 0.
- AC-2.4: `uv run mypy` exits 0 with mypy configured in strict mode over the `cottonwood` package and `tests`.
- AC-2.5: tool configuration (ruff, mypy, pytest) lives in `pyproject.toml`, and `uv.lock` is committed.

### US-3 — Versioned SQLite file from `migrate`
As the developer, I want `cottonwood migrate` to create or upgrade the database file through ordered plain-SQL migrations, so that later features add tables by adding one SQL file.

Acceptance criteria:
- AC-3.1: `uv run cottonwood migrate --db <path>` on a path that does not exist exits 0 and creates a SQLite file there whose `PRAGMA user_version` equals the number of the highest migration in `db/migrations/` (1 for the skeleton) and which has no tables in `sqlite_master` other than SQLite's internal ones.
- AC-3.2: running `migrate` a second time on the same file exits 0, applies nothing, and leaves `user_version` unchanged.
- AC-3.3: migrations are files named `NNN_<name>.sql` in `db/migrations/`, applied in numeric order, each only when its number is greater than the file's current `user_version`; a test with two temporary migration files shows both applied in order and `user_version` set to the higher number.
- AC-3.4: when the parent folder of `--db` does not exist, `migrate` exits 1 with a message naming the folder, and creates nothing.
- AC-3.5: `migrate` without `--db` uses the path in the `COTTONWOOD_DB` environment variable when set, otherwise `data/cottonwood.db`; the `data/` folder and SQLite files are git-ignored.

## Constraints & assumptions
- Follows `architecture.md` decisions 1, 2, 3 and 8: stdlib `sqlite3`, `PRAGMA user_version` runner, stdlib `argparse`, uv/pytest/ruff/mypy.
- Assumed (build question 1): Python 3.12, pinned in `.python-version`, `requires-python = ">=3.12"`.
- Assumed (build question 2): flat layout, package `cottonwood/` at the repo root as the architecture's tree shows, built with hatchling.
- Assumed (build question 3): the skeleton ships `db/migrations/001_baseline.sql` with no tables, so a migrated file is versioned (user_version 1) and empty; data-core adds its tables as `002_*.sql` rather than `001_init.sql`.
- Assumed (build question 4): default database path `data/cottonwood.db`, overridable with `COTTONWOOD_DB` or `--db`; config/pilot.yaml comes later.
- Assumed (build question 5): uv's cache is set to `.uv-cache/` in the repo (`[tool.uv] cache-dir`), git-ignored, so checks run inside the Claude Code Bash sandbox, which cannot write `~/.cache/uv`.
- Assumed (build question 6): mypy strict mode; ruff rule sets E, F, I, B, UP, with line length 100.
- The CLI makes no network calls (architecture NFR).

## Success metrics
- All four check commands exit 0 on the merged skeleton, and the `/sir:init` re-run reports them.
- The full test suite runs in well under the architecture's 60 s target.

## Open questions
- None blocking.
