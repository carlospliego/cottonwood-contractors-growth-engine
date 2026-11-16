# CCGE-117 — Credential scan: cover untracked files and stop exempting its own file

## Goal
Make the R-27 credential scan also catch a credential in a new untracked (not ignored) file and in its own test file, and say clearly when git is unavailable instead of failing obscurely.

## Inputs
tests/test_no_send_credentials.py:73-92,review finding F-testing-2 (run code/20261115-180811)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] The scan reads files from 'git ls-files --cached --others --exclude-standard', so an untracked, non-ignored file containing 'SMTP_PASSWORD=hunter2' is reported as PATH:LINE.
- [ ] The test file's own sample credential lines no longer need a self-exemption (for example they are built from parts at run time), and the scan includes tests/test_no_send_credentials.py.
- [ ] When git is not on PATH the scan test is skipped with a reason naming git, not an error.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
