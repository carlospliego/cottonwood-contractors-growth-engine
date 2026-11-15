# CCGE-010 — UTC time and contact normalization helpers

## Goal
Shared helpers store times as UTC ISO strings, show them in America/Denver, and normalize email, phone, domain and name keys.

## Inputs
Spec: `work/specs/data-core/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5)
Plan: `work/specs/data-core/plan.md`

## Constraints
_None._

## Plan
1. Add tzdata to project dependencies (uv add tzdata) and commit uv.lock.
2. Add cottonwood/timeutil.py: DENVER = ZoneInfo('America/Denver'); utc_now() -> str ('YYYY-MM-DDTHH:MM:SSZ'); to_utc_iso(dt) (aware datetimes only, converted to UTC, seconds precision); parse_utc(s) -> aware datetime (accepts the Z form); display_local(s) -> 'YYYY-MM-DD HH:MM -07:00' style string in Denver; local_date(s) -> date in Denver.
3. Add cottonwood/normalize.py: normalize_email, normalize_phone (US default +1, international + with 8-15 digits), normalize_domain, normalize_name; each raises ValueError naming the rule broken.
4. Add tests/test_timeutil.py (fixed instants around 2026-03-08 and 2026-11-01 DST changes, the 05:30Z local-date case, naive datetime rejected) and tests/test_normalize.py (table-driven valid and invalid inputs from the spec).
5. Run all checks.

## Acceptance Criteria
- [x] timeutil.utc_now() returns a string matching ^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$ and to_utc_iso rejects a naive datetime with ValueError; tests assert both.
- [x] timeutil.display_local('2026-01-15T19:00:00Z') contains '12:00' and '-07:00', and display_local('2026-07-15T18:00:00Z') contains '12:00' and '-06:00'; tests assert both.
- [x] timeutil.local_date('2026-11-16T05:30:00Z') == date(2026, 11, 15) and a test asserts it.
- [x] normalize_email('  Jane.Doe@Example.COM ') == 'jane.doe@example.com', and normalize_email raises ValueError for 'no-at-sign', 'a@b@c.com' and 'a@localhost'; tests assert each.
- [x] normalize_phone returns '+18015550134' for '(801) 555-0134', '801.555.0134', '1-801-555-0134' and '+1 801 555 0134', returns '+442071838750' for '+44 20 7183 8750', and raises ValueError for '555-0134' and '+12'; tests assert each.
- [x] normalize_domain('https://WWW.Example.com:443/about') == 'example.com' and normalize_name('  Jane   O\'Neil, Jr. ') == 'jane oneil jr'; tests assert both.
- [x] tzdata is a project dependency in pyproject.toml and uv.lock lists it.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy .` exit 0.

All criteria verified 2026-11-15.

## Depends on
_None._
