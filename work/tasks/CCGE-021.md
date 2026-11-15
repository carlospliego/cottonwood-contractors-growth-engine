# CCGE-021 — db.connect raises a general DatabaseError, not MigrationError

## Goal
Introduce a DatabaseError base class (MigrationError subclasses it) and have db.connect raise DatabaseError for open failures and a missing file.

## Inputs
cottonwood/db.py:58-75,review finding F-maintainability-3 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test asserts db.connect on a missing file raises an exception that is an instance of db.DatabaseError, and issubclass(db.MigrationError, db.DatabaseError) is True.

## Depends on
_None._
