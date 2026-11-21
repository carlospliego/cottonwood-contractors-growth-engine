# CCGE-087 — Test the report command's --out write failure and database read failure branches

## Goal
Cover _run_report's sqlite3.Error and OSError handlers so removing either, or returning success from them, fails a test.

## Inputs
cottonwood/cli.py:299-325 (_run_report),review finding F-testing-1 (run 20261115-161134),.sir/runs/fix/20261115-161134/F-testing-1.regression (proposed test; its fix apply failed at red because the mutant run imported unmutated code, see CCGE-063)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test runs `cottonwood report --period 7d --out` with the output path under a regular file and asserts exit 1, stderr starting 'error: could not write', and no Traceback.
- [x] A test makes building the report raise sqlite3.OperationalError and asserts exit 1, stderr starting 'error: could not read the database:', empty stdout and no output file.
- [x] Changing the report's sqlite3.Error handler in cottonwood/cli.py to return EXIT_OK makes the second test fail.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
