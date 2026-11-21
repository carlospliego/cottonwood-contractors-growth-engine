# CCGE-123 — Claims loader: refuse a claims file that is not valid UTF-8

## Goal
Report a claims file that cannot be decoded as UTF-8 as 'error: PATH: file: ...' with exit 1, instead of a UnicodeDecodeError traceback, for both 'claims' and 'approve claim'.

## Inputs
cottonwood/claims.py:81-86 (load_claims read_text),review finding F-correctness-3 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A claims file containing the bytes b'\xff\xfe' makes 'cottonwood claims --claims FILE' exit 1 with one stderr line starting 'error:' that names FILE.
- [x] The same file makes 'cottonwood approve claim service-area --approver Founder --reference r --claims FILE' exit 1 with a stderr line starting 'error: claims:' and appends no activity.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
