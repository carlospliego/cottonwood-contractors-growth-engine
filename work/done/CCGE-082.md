# CCGE-082 — Model cost against the cap, other costs and blocked sending

## Goal
Show model cost observed apart from estimated with month-to-date spend against a configured cap, other costs by category, and the open question that blocks sending when one is configured (R-28, R-29, R-30).

## Inputs
Spec: `work/specs/weekly-report/spec.md` (AC-5.1, AC-5.2, AC-5.3),Plan: `work/specs/weekly-report/plan.md`

## Constraints
Cost labels under ## Costs: Model cost, Model cost observed, Model cost estimated, Model cost month to date, Other costs, Other costs observed, Other costs estimated; a Category | Amount (USD) table only when there are entries (build assumption 9).,Money prints quantized to 0.01 ROUND_HALF_UP with no currency sign; sums stay exact (build assumption 9).,report.model_cost_cap_usd accepts an int, float or numeric string via Decimal(str()), 0 allowed; bool, non-finite, negative or non-numeric values raise ConfigError naming the key. This widens plan step 1 (float-free) to plan.md Components (a non-negative decimal number or string), because YAML parses 100.00 as a float (build assumption 9).,agent_runs: cost_estimated 1 is estimated, 0 or NULL observed; rows with NULL or non-decimal cost_usd are skipped (build assumption 9).,The final ## Sending blocked section says Sending is blocked until this open question is answered: and quotes the text with > ; with the key unset or blank the word blocked does not appear (build assumption 9).

## Plan
config.py: Config gains model_cost_cap_usd: Decimal | None = None and sending_blocked_by: str | None = None from an optional 'report' mapping; the cap accepts a non-negative int, float-free decimal string or int-like YAML number (str() then Decimal, finite, >= 0) else ConfigError naming report.model_cost_cap_usd; sending_blocked_by must be a string (blank -> None) else ConfigError.,config/pilot.yaml: commented 'report:' block documenting both keys, left unset.,report.py: model cost = Decimal(cost_usd) sum over agent_runs with non-null cost_usd and local_date(started_at) in the period, split by cost_estimated; MTD over the end date's Denver month 1st..end; render cap line 'Model cost month to date: X of CAP (REMAINING remaining)' or 'No model-cost cap configured (report.model_cost_cap_usd).'.,Other costs from events.cost_totals(period.start, period.end): total, observed, estimated, by category table.,'## Sending blocked' section quoting sending_blocked_by when set; otherwise no 'Sending blocked' text.,Tests tests/test_report_costs.py and config tests.

## Acceptance Criteria
- [x] With agent_runs rows started in the period costing 1.25 (cost_estimated 0) and 0.50 (cost_estimated 1), one started before the period but in the end date's Denver month costing 2.00, and one in the previous month costing 9.00, the report shows model cost 1.75 with observed 1.25 and estimated 0.50, and month-to-date 3.75; with config report.model_cost_cap_usd 100 it shows 3.75 against 100.00, and with no report.model_cost_cap_usd it states 'No model-cost cap configured'.
- [x] With counted cost_logged entries in the period of 49.00 observed (category formspark plan) and 10.00 estimated (category domain), plus a voided entry and one dated outside the period, the report shows other costs total 59.00, observed 49.00, estimated 10.00, and each category with its amount.
- [x] With config report.sending_blocked_by 'Q3: which domain sends outreach' the report contains a 'Sending blocked' section quoting that text; with the key absent or whitespace-only the report contains no 'Sending blocked' text.
- [x] A config whose report.model_cost_cap_usd is 'abc' or -5, or whose report.sending_blocked_by is a list, makes `cottonwood report --period 7d --config PATH` exit 1 with stderr starting 'error:' and naming the key; config/pilot.yaml still loads with both keys unset.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-081
