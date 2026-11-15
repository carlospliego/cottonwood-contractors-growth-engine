# CCGE-041 — Duplicate prompt goes to stdout, so it is invisible when stdout is redirected and the command appears to hang

## Goal
Write the prompt to stderr (print(prompt, end='', file=sys.stderr, flush=True); answer = sys.stdin.readline()) or require both stdin and stderr to be ttys.

## Inputs
cottonwood/cli.py:149-153,review finding F-correctness-9 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Write the prompt to stderr (print(prompt, end='', file=sys.stderr, flush=True); answer = sys.stdin.readline()) or require both stdin and stderr to be ttys. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
