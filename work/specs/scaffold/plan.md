# Scaffold — implementation plan

<!-- Written by /sir:plan from spec.md. Every decision traces to a story or constraint. -->

## Approach
**Context (Phase 0):**
- No application code exists; tracked files are sir scaffold and docs (`git ls-files`; `work/initiatives/cottonwood-growth-engine/architecture.md:6`).
- All sir checks are `null` (`.sir/config.yaml:11-16`); they are filled by the `/sir:init` re-run after merge, not by this feature.
- Target layout: `cottonwood/cli.py`, `cottonwood/db.py`, `db/migrations/NNN_*.sql`, `tests/` (`architecture.md:15-34`).
- Decisions to follow: stdlib `sqlite3` (`architecture.md:46`), `PRAGMA user_version` runner (`architecture.md:47`), `argparse` with `main(argv)` (`architecture.md:48`), uv/pytest/ruff/mypy (`architecture.md:53`); exit codes 0/1/2 (`architecture.md:81`).
- The sandbox already allows PyPI hosts (`.claude/settings.json` `sandbox.network.allowedDomains`), but uv's default cache `~/.cache/uv` is not writable there (observed "Operation not permitted"), hence a repo-local cache.
- `.gitignore` has only sir entries; it gains Python, uv, `data/` and `out/` entries.

Two tasks: first an installable package whose CLI parses arguments and whose four checks pass, then the migrations runner and `migrate` subcommand with their tests.

## Components & changes
| Area / file | Change | Serves |
|---|---|---|
| `pyproject.toml` | Project metadata, `cottonwood = "cottonwood.cli:entry"` script, hatchling build, dev group (pytest, ruff, mypy), `[tool.ruff]`, `[tool.mypy]` strict, `[tool.pytest.ini_options]`, `[tool.uv] cache-dir = ".uv-cache"` | US-1, US-2 |
| `.python-version`, `uv.lock` | Pin 3.12; lock file committed | US-2 |
| `.gitignore` | `.venv/`, `.uv-cache/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `data/`, `out/`, `*.db`, `*.sqlite3` | US-2, US-3 |
| `cottonwood/__init__.py`, `cottonwood/__main__.py` | Package, `python -m cottonwood` | US-1 |
| `cottonwood/cli.py` | `build_parser()`, `main(argv) -> int`, `entry()` calling `sys.exit(main())`; subcommands registered with a handler per command; argparse errors return 2 | US-1, US-3 |
| `cottonwood/db.py` | `MIGRATIONS_DIR`, `default_db_path()`, `discover_migrations(dir)`, `migrate(db_path, migrations_dir) -> (from, to)` | US-3 |
| `db/migrations/001_baseline.sql` | Comment-only baseline, no tables | US-3 |
| `tests/test_cli.py`, `tests/test_migrate.py` | pytest tests | US-1, US-2, US-3 |

## Data & interfaces
- `cottonwood migrate [--db PATH]`: exit 0 and prints `database <path> at version <n> (applied <k>)`; exit 1 with `error: folder does not exist: <dir>` when the parent is missing.
- DB path resolution: `--db` > `$COTTONWOOD_DB` > `data/cottonwood.db` (relative to the current directory).
- Migration file name: `^(\d{3})_[a-z0-9_]+\.sql$`; each applied with `executescript` inside a transaction followed by `PRAGMA user_version = N`. Migrations directory resolves to `<repo>/db/migrations` (relative to the package file's parent) and is a parameter for tests.
- `main(argv: Sequence[str] | None) -> int`: argparse's `SystemExit` is caught and turned into its code (2 for usage errors, 0 for `--help`).

## Risks & rollback
| Risk | Mitigation | Rollback |
|---|---|---|
| Checks fail inside the sandbox (uv cache, PyPI) | Repo-local `cache-dir`; PyPI hosts allowed already | Run checks outside the sandbox |
| Baseline migration numbering differs from architecture's `001_init.sql` | Recorded as assumption; data-core starts at 002 | Rename files before any real database exists |
| `executescript` commits implicitly | Use explicit `BEGIN`/`COMMIT` inside the script string, plus user_version in the same transaction | Re-run migrate on a fresh file |

## Test strategy
| AC | How | Command |
|---|---|---|
| AC-1.1 | subprocess `uv run cottonwood --help` output check, plus `main(["--help"])` returns 0 in tests | `uv run cottonwood --help`; `uv run pytest tests/test_cli.py` |
| AC-1.2 | tests: `main([])` and `main(["not-a-command"])` return 2 | `uv run pytest tests/test_cli.py` |
| AC-1.3 | test calls `main([...])` and asserts an int return | `uv run pytest tests/test_cli.py` |
| AC-2.1 | suite has CLI and migrate tests and passes | `uv run pytest` |
| AC-2.2 / 2.3 / 2.4 | run the tools | `uv run ruff check`; `uv run ruff format --check`; `uv run mypy` |
| AC-2.5 | inspect `pyproject.toml`, `git ls-files uv.lock` | — |
| AC-3.1 / 3.2 | tests on `tmp_path`, query `PRAGMA user_version` and `sqlite_master` | `uv run pytest tests/test_migrate.py` |
| AC-3.3 | test with a temporary migrations dir holding `001_a.sql`, `002_b.sql` | `uv run pytest tests/test_migrate.py` |
| AC-3.4 | test with missing parent dir: exit 1, message names the dir, no file | `uv run pytest tests/test_migrate.py` |
| AC-3.5 | test with `monkeypatch.setenv("COTTONWOOD_DB", ...)` and with `chdir` to tmp for the default; `git check-ignore data/cottonwood.db` | `uv run pytest tests/test_migrate.py` |

## Sequencing
1. T-01 package, tooling and CLI skeleton — everything else needs a passing toolchain.
2. T-02 migrations runner and `migrate` command (depends on T-01).
