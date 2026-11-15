# CCGE-068 — Require a host in R-16 procurement URLs

## Goal
Refuse procurement URLs whose netloc has no hostname, such as 'http://:80' or 'https://user@' (review 20261115-091006 F-correctness-7).

## Inputs
cottonwood/events.py:159-162 _is_http_url (F-correctness-7)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] log-event with --stage buyer_need_confirmed and --procurement-url 'http://:80' exits 1 and writes nothing, asserted by a test.

## Depends on
_None._
