# Assumptions — events-and-stages

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Which parts of phase 3 does events-and-stages build, and which wait for weekly-report?
- **Answer:** events-and-stages builds log-event (R-14 to R-17), log-time and log-cost (the recording half of R-30), and an events module that gives the counted (non-void, non-test) activities and the time and cost totals for a date range. The report command itself (R-28, R-29, R-31 for report) is weekly-report.
- **Why:** The roadmap names the two features; weekly-report is the report, so it gets the counting surface it needs from this feature.

## A-2 · plan
- **Question:** What is log-event's interface and how is the event time given?
- **Answer:** cottonwood log-event <lead-id> <type> --at TIME [--stage STAGE] [--note TEXT] [--need TEXT] [--procurement-url URL] [--actor NAME] [--db PATH]. --at is required and takes the same formats as log-inbound --received (America/Denver 'YYYY-MM-DD HH:MM' or UTC ending in Z); a time later than now is refused. An unknown lead id exits 1 with 'error: no lead <id>'.
- **Why:** Events are logged after they happen via the relay; a silent default to now would misdate them, and a future time is almost always a typo that would distort the report.

## A-3 · plan
- **Question:** How is a stage change stored and validated (R-14, R-15)?
- **Answer:** leads.stage is updated in place and a stage_change activity is appended with payload {from, to, event_activity_id} naming the event, in the same transaction as the event. A stage outside the lead type's R-14 list, or equal to the current stage, exits 1 naming the allowed stages and writes nothing. No transition order is enforced: any stage in the type's list may follow any other.
- **Why:** R-14 lists values but no transition graph; leads is not append-only, and the activities hold the history.

## A-4 · plan
- **Question:** Are event types tied to lead types, and do won/lost set the stage automatically?
- **Answer:** Every R-15 event type is accepted on every lead type, and no event moves the stage unless --stage is given. The note type requires --note; --note is optional for the others.
- **Why:** R-15 makes the stage move optional and does not tie event types to lead types.

## A-5 · plan
- **Question:** How does log-event enforce R-16 (buyer_need_confirmed only through an event stating a confirmed need or an accessible active procurement URL)?
- **Answer:** --stage buyer_need_confirmed requires --need (non-blank text stating the confirmed need) or --procurement-url (an absolute http or https URL), and both are recorded in the event payload; without either it exits 1 and writes nothing. --need or --procurement-url with any other stage, or without --stage, exits 1. The tool cannot check that a procurement is accessible or active; the developer attests to it by giving the URL.
- **Why:** Keeps the qualification rule deterministic and the KPI's numerator honest; checking a URL live would need network access the CLI does not have.

## A-6 · plan
- **Question:** Where do an event's free-text note and need statement go?
- **Answer:** In the event activity's payload. This is the same R-35 vs R-17 conflict recorded as data-core assumption 8 (append-only payload text cannot be cleared on a deletion request), and it is listed in the spec's Open questions for the founder; the help text says not to put contact details in notes.
- **Why:** There is no other place for event text in the 7-table schema, and R-15's note type needs text.

## A-7 · plan
- **Question:** What may a correction void, and what happens to a stage change caused by the voided event?
- **Answer:** log-event <lead-id> correction --voids <activity-id> --at TIME [--note REASON] voids one activity of that lead that is an R-15 event and not already void; a stage_change, correction or inquiry_logged target, another lead's activity, or a missing id exits 1. --stage with correction exits 1. If the voided event caused a stage change, that change must be the lead's latest effective one: the lead returns to its from-stage and a stage_change activity naming the correction is appended. If a later effective stage change exists, the correction is refused naming it.
- **Why:** Keeps the lead's stage consistent with its non-void history while activities stay append-only (R-17).

## A-8 · plan
- **Question:** What exactly counts as a counted activity, and where is that rule defined?
- **Answer:** An activity counts when it is not a correction, no correction voids it, it is not a stage_change whose causing event is void, and its lead is not a test lead (entries with no lead, such as time and cost, count). The rule is one SQL definition in cottonwood/events.py, with no new migration.
- **Why:** R-17 says void activities are excluded from all counts and R-3 excludes tests; one definition lets the report reuse it, and no migration means no schema-version churn in existing tests.

## A-9 · plan
- **Question:** What does log-time take and store (R-30)?
- **Answer:** cottonwood log-time <hours> --date YYYY-MM-DD --category TEXT [--person founder|developer] [--estimated] [--note TEXT] [--actor] [--db]. Hours is a decimal > 0 and <= 24 with at most 2 decimal places; the date is an America/Denver date not after today; the category is free text, stripped and lowercased, and must not be blank; --person defaults to founder. It appends a time_logged activity with no lead, occurred_at at the start of that Denver date in UTC, and payload {date, hours, category, person, estimated, note}.
- **Why:** R-30 gives no category list, so none is invented; the architecture measures developer logging time with log-time, so a person label keeps developer hours out of the KPI's founder hours; estimated supports R-29's observed-vs-estimated split.

## A-10 · plan
- **Question:** What does log-cost take and store, and does R-9's money basis apply?
- **Answer:** cottonwood log-cost <amount> --date YYYY-MM-DD --category TEXT [--estimated] [--note TEXT] [--actor] [--db]. Amount is USD, a decimal > 0 with at most 2 decimal places, stored as exact decimal text; date and category follow log-time's rules. It appends a cost_logged activity with no lead and payload {date, amount_usd, category, estimated, note}. R-9's basis applies to lead money values; a cost records estimated true or false instead. Skill-run model cost comes from record-run, not log-cost.
- **Why:** Spend is an observed or estimated outlay, not a buyer or founder valuation; R-29 needs the estimated flag.

## A-11 · plan
- **Question:** How is a wrong time or cost entry corrected, given R-17's log-event form needs a lead id?
- **Answer:** log-time --voids <activity-id> and log-cost --voids <activity-id> (given instead of the amount, --date and --category) append a correction activity with no lead that voids a time_logged or cost_logged entry respectively; a wrong type, a missing id or an entry already void exits 1.
- **Why:** Founder hours are the KPI's denominator, so mistakes must be correctable without editing activities.

## A-12 · plan
- **Question:** What totals does this feature provide for the report?
- **Answer:** events.time_totals(conn, start, end) and events.cost_totals(conn, start, end) take inclusive America/Denver dates and sum counted entries exactly (Decimal), split by person (time) and by category and observed vs estimated; days with no entries total 0.
- **Why:** R-30 says the report totals them; weekly-report reuses these instead of re-deriving the void and test rules.

## A-13 · plan
- **Question:** What do the new commands print, and how do they fail?
- **Answer:** On success, one line naming the activity id, type, lead and Denver time, plus 'stage <from> -> <to>' when the stage moved. Validation errors exit 1 with 'error: <field>: <reason>' before the database is opened, argparse usage errors exit 2, and a missing or unmigrated database or an SQLite error exits 1 with 'error: ...' and no traceback; nothing is written on any failure. The commands never migrate on their own.
- **Why:** Matches log-inbound's conventions (cli.py exit codes) so the operator sees one style.

## A-14 · do
- **Question:** CCGE-056: EventError formats as 'field: message', which would print 'error: lead: no lead 999', but AC3 requires 'error: no lead 999'. How should the missing-lead message print, and is a blank --actor allowed?
- **Answer:** A missing lead raises LeadNotFoundError, a subclass of EventError whose str is just 'no lead <id>', so the CLI prints 'error: no lead 999'. All other EventErrors print 'error: <field>: <message>'. A blank or whitespace-only --actor is refused with 'actor: must not be empty', as log-inbound does.
- **Why:** This meets the AC wording without changing how other validation errors print, and keeps log-inbound's actor rule.

## A-15 · do
- **Question:** CCGE-058: which occurred_at do the correction and its stage-revert stage_change carry, and may a correction's --at be earlier than the event it voids?
- **Answer:** Both rows carry the correction's --at. A correction whose --at is earlier than the voided activity's occurred_at is refused (exit 1, field 'at'), so a revert never sorts before the change it undoes. tests/test_events.py::test_unknown_type_is_a_usage_error drops 'correction' from its bad-type list, because correction becomes a valid type; this is recorded via sir task allow-test.
- **Why:** A correction happens after what it corrects. Keeping that order keeps the latest-effective-stage-change rule (ordered by occurred_at, id) consistent.

## A-16 · do
- **Question:** CCGE-058 stopped at verifying (blocked on the AC7 placeholder, now reworded and repinned by the owner). Resume from verifying or restart?
- **Answer:** Resume from verifying in the existing worktree .claude/worktrees/ccge-058 (base 6daf186); re-run the checks first.
- **Why:** Recommended answer: the implementation is complete and checks passed; only the contract lint blocked verification.

## A-17 · do
- **Question:** CCGE-059 gaps from the survey: (a) --voids combined with --person or --estimated; (b) the shape time_totals/cost_totals return; (c) exponent input like '1e1' for hours/amount.
- **Answer:** (a) --voids is also exclusive with --person and --estimated (exit 1, field 'voids'); --note with --voids is the correction's reason. (b) frozen dataclasses TimeTotals(total, by_person, observed, estimated) and CostTotals(total, by_category, observed, estimated) of Decimal, dicts keyed by person/category. (c) hours and amounts must be plain decimals (digits with an optional fraction); exponent forms like '1e1' are refused with exit 1, and the stored text is the input's canonical Decimal string.
- **Why:** Recommended: refusing ambiguous combinations matches the contract's --voids exclusivity; frozen dataclasses match the module's style; refusing exponents avoids the stringification bug tracked as CCGE-042.

## A-18 · fix
- **Question:** F-testing-2 (medium, log-time/log-cost write failures untested): the proposed regression test passed on the mutant that removes the except sqlite3.Error branch in _run_entry, so sir fix apply failed at 'red'. Force it, retry, or file it?
- **Answer:** Filed as a task, not forced; the build goes on.
- **Why:** Build mode: a failed fix below high is never forced; it is filed as a task with a draft contract.

## A-19 · fix
- **Question:** F-testing-1 (medium) also failed sir fix apply at 'red': its test passed on the mutant. Cause found: the uv editable install's .pth points at the main checkout and tests/ has no __init__.py, so in sir's mutant copy `import cottonwood` loads the unmutated main-checkout code; every coverage (mutant-only) fix in this repo fails red regardless of the test. Change pytest config to import the local tree, or file?
- **Answer:** File F-testing-1 like F-testing-2 (not forced), and file a separate task to make tests import the checkout they run in (e.g. pytest pythonpath or a non-editable layout) so mutant checks work.
- **Why:** Build mode never forces a failed fix below high; changing the project's test import setup inside the fix stage would be an unreviewed out-of-scope change made only to get past a gate.
