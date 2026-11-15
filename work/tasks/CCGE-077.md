# CCGE-077 — Assert --actor is stored on entries, voids and corrections

## Goal
Cover that --actor reaches the actor column of time and cost entries, their voids, corrections and revert stage changes (review 20261115-091006 F-testing-4).

## Inputs
cottonwood/events.py:595-606 (F-testing-4)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test passes --actor founder to log-time, log-cost, a --voids and a reverting correction and asserts actor 'founder' on every row written, including the revert stage_change.

## Depends on
_None._
