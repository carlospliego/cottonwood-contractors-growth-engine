# CCGE-063 — Make tests import the checkout they run in

## Goal
The uv editable install's .pth points at the main checkout and tests/ has no __init__.py, so tests run from a copy (sir mutant checks, worktrees without their own venv) import the main checkout's cottonwood package; sir fix's red step therefore can never kill a mutant here (F-testing-1 and F-testing-2 failed for this reason in review 20261115-091006).

## Inputs
pyproject.toml [tool.pytest.ini_options],.venv site-packages .pth for the editable install,sir fix apply output for F-testing-1 and F-testing-2 in review 20261115-091006

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] From a copy of the repository in another directory, running `uv run pytest` with a deliberate break in that copy's cottonwood/events.py makes a test fail, shown by a test or a documented command in the runbook; and the full suite still passes in the main checkout.

All criteria verified 2026-11-20.

## Depends on
_None._
