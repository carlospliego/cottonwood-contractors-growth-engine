# CCGE-146 — Apply the founder brief's answers to the pilot config and claims library

## Goal
Set the sending and review values the developer answered in the 2026-11-15 founder brief, record that sending stays blocked on the founder's sender identity and postal address, and reword the claims library from the website (cottonwoodcontractors.com) as the source of truth, leaving every claim unverified until the founder confirms in writing.

## Inputs
config/pilot.yaml,config/claims.yaml,cottonwood/config.py,cottonwood/claims.py,tests/test_claims.py,tests/test_report_costs.py,tests/test_sending_config.py,tests/test_review_config.py,https://cottonwoodcontractors.com/service-areas/,https://cottonwoodcontractors.com/projects/

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] config.load_config on config/pilot.yaml gives review.max_evidence_age_days 90, sending.opt_out_line exactly 'Don't want to hear from us? Reply "unsubscribe" and we will never contact you again.', sending.ad_identification exactly 'This is a business solicitation from Cottonwood Contractors.', sending.sender_identity and sending.postal_address both empty, report.sending_blocked_by exactly 'Founder: sender identity and business postal address', and model_cost_cap_usd None; a test in tests/ asserts each of these values.
- [x] config/claims.yaml loads with claim ids fashion-place-attribution, service-area, license-classification, insurance-bonding, prior-company-experience and website-projects in that order, every one with status unverified and verified_by and verified_at null; the service-area text names Salt Lake County and not Davis, Weber or Utah County; the website-projects text names the Coffered Ceiling Kitchen, Spa-Inspired Primary Bathroom, Primary Bathroom in Lehi, Lower-Level Family Room and Open-Concept Great Room; the evidence of fashion-place-attribution, service-area and website-projects each contains a https://cottonwoodcontractors.com/ URL; a test in tests/ asserts each of these.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.
- [x] The changes to existing test `tests/test_claims.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the shipped config now carries the founder brief answers (CCGE-146), so the test that pinned the shipped values as unset moves to the new values).
- [x] The changes to existing test `tests/test_report_costs.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the shipped config now carries the founder brief answers (CCGE-146), so the test that pinned the shipped values as unset moves to the new values).
- [x] The changes to existing test `tests/test_sending_config.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the shipped config now carries the founder brief answers (CCGE-146), so the test that pinned the shipped values as unset moves to the new values).
- [x] The changes to existing test `tests/test_review_config.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the shipped config now carries the founder brief answers (CCGE-146), so the test that pinned the shipped values as unset moves to the new values).

All criteria verified 2026-11-15.

## Depends on
_None._
