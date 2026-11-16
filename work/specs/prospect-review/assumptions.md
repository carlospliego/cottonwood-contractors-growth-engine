# Assumptions — prospect-review

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Where do the yes/no/unknown checklist answers in review come from?
- **Answer:** An optional `checklist` object in each research record, stored on the lead (migration 005 leads.checklist); keys must be configured items for the record's type; missing answers show unknown.
- **Why:** The research skill already writes research records, so answers arrive with the evidence; rejecting unknown keys catches typos instead of silently showing unknown.

## A-2 · plan
- **Question:** How does set-eligibility check an 'unambiguous identity' (R-8), and where is the basis recorded?
- **Answer:** Deterministic: the contact has a name and an email and no other not-deleted contact shares its email_norm. The source URL is stored on contacts.source_url; the eligibility_set payload holds only from, to and basis kind (public-source-url or manual).
- **Why:** A checkable rule beats free text; keeping URLs out of append-only payloads follows R-35 and the prospect-import payload rule.

## A-3 · plan
- **Question:** What happens when a lead is hand-reviewed a second time?
- **Answer:** Refused unless --replace; --replace appends a correction voiding the earlier hand_review and a new hand_review, so the report counts one result per lead.
- **Why:** Reuses the existing correction mechanism (append-only, R-17) and keeps report counts honest.

## A-4 · plan
- **Question:** Which checklist items go in config/pilot.yaml, and is a max evidence age set?
- **Answer:** Six direct-candidate and five relationship-prospect items from SPEC.md section 9 (founder time is its own column); review.max_evidence_age_days is left unset and review says 'not configured' until the founder decides.
- **Why:** SPEC.md section 9 is the source the spec names; the max age is an open founder question.

## A-5 · do
- **Question:** CCGE-103 survey: should prospects-import fail when the config file is missing, and does an absent stored checklist answer count as a difference on re-import?
- **Answer:** An explicit missing --config is an error; a missing default config falls back to empty checklists (every checklist key rejected). An incoming answer against an absent stored one prints a checklist.KEY differs line.
- **Why:** Keeps existing imports working without a config while never silently accepting unconfigured keys; matches the existing difference rule for other fields.

## A-6 · fix
- **Question:** F-testing-1 (medium, coverage) failed its red proof: sir fix apply reported the regression test passes on the mutant of review._answers. Stop, or file it?
- **Answer:** Filed as a task (below high, so not a stop) with the proposed test and the mutant in its inputs.
- **Why:** The fix stage rule files a failed fix below high. The likely cause is the known CCGE-063 issue (trial copies import the unmutated editable install; CCGE-102 was filed the same way); a manual PYTHONPATH check was blocked by the policy hook, so the cause is unconfirmed.
