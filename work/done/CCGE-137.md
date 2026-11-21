# CCGE-137 — Reply.eligibility shadows the eligibility module

## Goal
Rename the Reply dataclass field so it no longer shares the name of the imported eligibility module (review 20261115-191126 F-maintainability-2).

## Inputs
cottonwood/send.py class Reply

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] In cottonwood/send.py the Reply dataclass has no field named eligibility, and uv run pytest and uv run mypy . pass.

All criteria verified 2026-11-21.

## Depends on
_None._
