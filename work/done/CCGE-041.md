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
- [x] Write the prompt to stderr (print(prompt, end='', file=sys.stderr, flush=True); answer = sys.stdin.readline()) or require both stdin and stderr to be ttys. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.
- [x] The changes to existing test `tests/test_inbound_duplicates.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The tty prompt tests patch builtins.input; the prompt now goes to stderr and the answer is read with sys.stdin.readline, so the three tests feed a fake tty stdin instead and assert the prompt on stderr. The answers they check (y/YES/' yes ' save; n/''/maybe refuse; EOF refuses) are unchanged).

All criteria verified 2026-11-20.

## Depends on
_None._
