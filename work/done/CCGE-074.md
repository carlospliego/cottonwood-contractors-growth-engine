# CCGE-074 — Rename _void_entry_conflict to say it also checks required options

## Goal
Make the helper's name match both of its jobs (review 20261115-091006 F-maintainability-8).

## Inputs
cottonwood/cli.py:452-466 _void_entry_conflict (F-maintainability-8)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] cottonwood/cli.py no longer defines _void_entry_conflict; the check is named for both jobs (for example _entry_option_problem) or split into two functions, and the existing tests pass.

All criteria verified 2026-11-21.

## Depends on
_None._
