# CCGE-001 — Python package, tooling and CLI skeleton

## Goal
An installable cottonwood package with an argparse CLI whose ruff, format, mypy and pytest checks pass through uv run.

## Inputs
Spec: `work/specs/scaffold/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-2.2, AC-2.3, AC-2.4, AC-2.5)
Plan: `work/specs/scaffold/plan.md`

## Constraints
_None._

## Plan
1. Add pyproject.toml: project cottonwood, requires-python >=3.12, script cottonwood = cottonwood.cli:entry, hatchling build with packages [cottonwood], dev dependency group pytest/ruff/mypy, [tool.ruff] line-length 100 with lint select E,F,I,B,UP, [tool.mypy] strict with files cottonwood and tests, [tool.pytest.ini_options] testpaths tests, [tool.uv] cache-dir .uv-cache.
2. Add .python-version (3.12) and extend .gitignore with .venv/, .uv-cache/, __pycache__/, .pytest_cache/, .mypy_cache/, .ruff_cache/, dist/, data/, out/, *.db, *.sqlite3.
3. Add cottonwood/__init__.py (__version__), cottonwood/__main__.py, cottonwood/cli.py with build_parser() using required subparsers, main(argv) -> int that turns argparse SystemExit into its code, and entry() calling sys.exit(main()). Register a placeholder-free subcommand table so later commands plug in.
4. Add tests/test_cli.py: --help returns 0 and lists the program; no subcommand and an unknown subcommand return 2; main returns an int.
5. Run uv lock / uv sync and commit uv.lock; run all four checks.

## Acceptance Criteria
- [x] `uv run cottonwood --help` exits 0 and its output contains `cottonwood`.
- [x] `uv run cottonwood` with no subcommand and `uv run cottonwood not-a-command` each exit with code 2.
- [x] `cottonwood.cli.main([...])` returns the exit code as an int and a test in tests/test_cli.py asserts it.
- [x] `uv run ruff check` exits 0.
- [x] `uv run ruff format --check` exits 0.
- [x] `uv run mypy` exits 0 with `strict = true` in pyproject.toml's [tool.mypy] and both `cottonwood` and `tests` checked.
- [x] pyproject.toml holds the ruff, mypy and pytest configuration, and uv.lock exists in the repo.
- [x] `uv run pytest` exits 0.

All criteria verified 2026-11-15.

## Depends on
_None._
