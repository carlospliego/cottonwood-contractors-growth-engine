# CCGE-009 — Refuse a database newer than the known migrations

## Goal
migrate refuses a database whose user_version is above the highest migration number instead of reporting success.

## Inputs
cottonwood/db.py:migrate (review finding F-correctness-3, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] With a database at user_version 5 and migrations 001 only, `cottonwood migrate --db` on that file exits 1 and stderr names both the database version and the newest known migration number; a test asserts it.

## Depends on
_None._
