# Assumptions — weekly-report

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** What period does report cover and where does it write? (--period anchoring, --from/--to, output file)
- **Answer:** --period 7d|30d covers the 7 or 30 America/Denver dates ending today inclusive; --from/--to are inclusive Denver dates and exclusive with --period; from later than to, a half pair, or no period exits 1. An activity is in the period when its occurred_at falls on a period date in Denver; time/cost entries use their payload date; agent runs use started_at. Output goes to stdout, or with --out PATH to a file (parents created, 'report written: PATH'), following review's conventions.
- **Why:** R-28 gives the flags and inclusive Denver dates; anchoring at today matches the weekly flow, and copying review's --out keeps one style (R-31).

## A-2 · plan
- **Question:** How is the same-working-day acknowledgement target judged, given no working days are defined anywhere?
- **Answer:** Working days are Monday-Friday in America/Denver with no holidays. A non-test inquiry received in the period is within target if its earliest counted acknowledgement is on the same Denver date (received on a working day) or by the end of the next working day (received on a non-working day); otherwise outside target; no counted acknowledgement means not acknowledged.
- **Why:** The spec names the target but not working days; whole weekdays are the simplest deterministic rule, and holidays/business hours stay an open question for the founder.

## A-3 · plan
- **Question:** How are conversation metrics and the KPI counted (distinct leads vs entries, events vs stage entries, which founder hours)?
- **Answer:** Qualified direct conversations = distinct non-test leads with a counted stage_change into buyer_need_confirmed in the period (correction reverts excluded). Partner conversations, remote screens, walkthroughs, proposals and wins = counted events of those types. KPI = (qualified + partner conversations) / total founder hours (observed + estimated, both shown), 2 decimals, n/a at 0 hours; developer hours shown separately.
- **Why:** R-28 says 'leads entering' buyer_need_confirmed and names partner_conversation events; counting events (not stage entries) for walkthrough/proposal/won avoids double counting when both are logged; whether the KPI should use observed hours only is an open founder question.

## A-4 · plan
- **Question:** How does the report count metrics whose rows later features write (research, hand review, approvals, drafts, sends, gate violations, replies, opt-outs, referrals, data quality, model cost), when architecture.md names the activity types but no payload keys, and where do the cost cap and the blocked-sending statement come from?
- **Answer:** Count the architecture's activity types through COUNTED_ACTIVITIES_SQL (imported, hand_review, approval, draft_prepared, sent, gate_violation, reply, suppressed, import_rejected) so they print 0 until those features write them. Payload keys set here as the contract: hand_review.result (relevant|irrelevant|fabricated) and reply.reply_type (interested|not_now|not_relevant|referral|opt_out|bounce|other). Model cost sums agent_runs.cost_usd by started_at, split by cost_estimated, with month-to-date against new optional config key report.model_cost_cap_usd; new optional key report.sending_blocked_by holds the blocking open-question text the report quotes.
- **Why:** The roadmap's phase 3 exit needs every R-28 metric now; reading the named types keeps the report unchanged when later features land, and config keys are the only place the report can learn the cap and a blocker without a database change.

## A-5 · do
- **Question:** CCGE-079 survey: config loading before report keys exist, NULL received_at, exact label text, and unknown channel/segment values?
- **Answer:** Load config (--config / $COTTONWOOD_CONFIG / config/pilot.yaml) after parsing the period and before connecting, ConfigError -> exit 1; leave inquiries with NULL received_at out of the counts and the ack target; labels are module constants: 'Inquiries', 'Channel KEY', 'Segment KEY', 'Acknowledged within target', 'Acknowledged outside target', 'Not acknowledged', 'Missed calls', 'Returned calls' as '- Label: N' lines; an unknown channel or segment counts in the total but not the breakdown, like review (CCGE-046 fixes both).
- **Why:** Surveyor recommendations: follows the plan, avoids a crash on nullable received_at, gives later tasks and tests stable labels, and keeps review and report agreeing.

## A-6 · do
- **Question:** CCGE-079 AC2 was wrong: "`report --from 2026-11-01 --to 2026-11-15` on a database with a counted missed_call event at 2026-11-16T06:59:59Z and another at 2026-11-16T07:00:00Z reports missed calls 1, and adding a third missed_call at 2026-11-01T07:00:00Z makes it 2 while one at 2026-11-01T06:59:59Z does not."
- **Answer:** amended to: "`report --from 2026-11-01 --to 2026-11-15` on a database with a counted missed_call event at 2026-11-16T06:59:59Z and another at 2026-11-16T07:00:00Z reports missed calls 1, and adding a third missed_call at 2026-11-01T06:00:00Z makes it 2 while one at 2026-11-01T05:59:59Z does not."
- **Why:** DST ends 2026-11-01 at 08:00Z, so 2026-11-01T06:59:59Z is 00:59:59 MDT on Nov 1 (inside the period) under the spec's rule that an activity is in the period when its occurred_at falls on a period date in America/Denver (spec AC-1.2 and Constraints; plan Data & interfaces). Denver midnight on Nov 1 is 06:00:00Z; 05:59:59Z is 23:59:59 MDT on Oct 31. Only the start-boundary instants change.

## A-7 · do
- **Question:** CCGE-080 survey: label text for conversations/KPI/hours, how hours and the KPI print, and where the founder observed/estimated split comes from?
- **Answer:** Labels: 'Qualified direct conversations', 'Partner conversations', 'Remote screens', 'Walkthroughs', 'Proposals', 'Won projects', 'KPI (qualified + partner) per founder hour' under '## Conversations and KPI'; 'Founder hours', 'Founder hours observed', 'Founder hours estimated', 'Developer hours' under '## Hours'. Hours print as str() of the exact Decimal sum; the KPI is quantized to 0.01 ROUND_HALF_UP, 'n/a' at 0 founder hours. The founder split is summed in report.py from events._entries_in_range (the same entries time_totals reads) filtered to person founder, cross-checked in a test against time_totals.by_person['founder'].
- **Why:** Surveyor recommendations: stable labels for tests and later tasks, exact sums as stored (R-29), the KPI format in AC-3.4, and one source of entries so the split cannot drift from the totals.

## A-8 · do
- **Question:** CCGE-081 survey: label text and layout for the funnel sections, unknown hand-review results, partner naming, and how referred leads are counted?
- **Answer:** '- Label: value' lines from module constants: 'Researched direct candidates', 'Researched partner firms', 'Hand review MOTION RESULT' and 'Hand review MOTION total' (an unknown result is in the total only), 'Approvals', 'Prepared drafts', 'Sends', 'Gate violations', 'Replies TYPE' (unknown or missing type counts as other), 'Opt-outs', 'Data-quality failures', 'Referred leads'. Referrals add a pipe table 'Partner lead | Name | Referred leads' ordered by partner id, cells escaped with review._cell; the name is the partner's non-blank organization name, else contact name, else '—'. A referred lead counts once however many imported/inquiry_logged activities it has in the period; any lead may be the referrer, and only the referred lead's is_test filters.
- **Why:** Surveyor recommendations: matches the existing Channel/Segment line pattern so every combination prints and parses, follows plan.md's payload contract for unknown values, and counts leads (not activities) as AC-4.5 says.

## A-9 · do
- **Question:** CCGE-082 survey: cost labels and money format, the cap line, which YAML cap values are accepted, sending_blocked_by validation and text, and odd agent_runs rows?
- **Answer:** Under '## Costs': 'Model cost', 'Model cost observed', 'Model cost estimated', 'Model cost month to date' (value 'MTD of CAP (R remaining)' or '(R over cap)' with a cap; otherwise 'MTD' plus the line 'No model-cost cap configured (report.model_cost_cap_usd).'), 'Other costs', 'Other costs observed', 'Other costs estimated', and a 'Category | Amount (USD)' table only when there are entries. Money prints quantized to 0.01 ROUND_HALF_UP with no currency sign; sums stay exact. report.model_cost_cap_usd accepts an int, float or numeric string (via Decimal(str())), 0 allowed; bool, non-finite, negative or non-numeric raise ConfigError naming the key. report.sending_blocked_by must be a string (blank means unset), else ConfigError; when set, a final '## Sending blocked' section says 'Sending is blocked until this open question is answered:' and quotes the text with '> '. agent_runs: cost_estimated 1 is estimated, 0 or NULL observed; rows with NULL or non-decimal cost_usd are skipped.
- **Why:** Surveyor recommendations: unique labels for tests, exact R-29 sums with readable money, plan.md's 'non-negative decimal number or string' for the cap (YAML turns 100.00 into a float), and no traceback on rows no writer produces yet.

## A-10 · fix
- **Question:** F-testing-1 (medium: report --out write and database read failure branches untested) failed sir fix apply at red: the regression test passed on the mutant because the mutant run imports unmutated code (known issue CCGE-063). Force it, or file it?
- **Answer:** Filed as a task with the proposed test attached; not forced.
- **Why:** Build mode never forces a failed fix; below high severity a failed fix is filed as a task and recorded as an assumption.
