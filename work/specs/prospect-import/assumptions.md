# Assumptions — prospect-import

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Which requirements does prospect-import cover, given phase 4 also has prospect-review and research-skill?
- **Answer:** R-5, R-6, R-7, R-9, R-12 (referred_by on import), R-24's import check and R-25's validation, plus the record schema the research skill will use. set-eligibility, mark-reviewed, review queues and evidence age (R-8 command, R-10, R-11, R-13) go to prospect-review; the skill, record-run and R-26/R-27 to research-skill.
- **Why:** architecture.md puts prospects-import in prospects.py and validation in validate.py; the brief names the other two features as built separately.

## A-2 · plan
- **Question:** Record format: what does a research record look like in JSON and CSV?
- **Answer:** JSON: a top-level array of records {record_id?, type, organization{name, domain?, type?, category?}, contact?{name?, email?, phone?, role?, source_url?}, property_location?, verified_facts[string], hypothesis string, next_action?, founder_time_h?, value?{amount, basis}, referred_by? lead id, is_test?, evidence[{url, observed_at YYYY-MM-DD, published_at?, excerpt or observation, kind fact|hypothesis default fact}]}. CSV: one record per row with flattened columns (organization_name, contact_email, evidence_url, ...), one evidence item per row, verified_facts newline-separated; empty cells are absent; rows are converted to the JSON shape and validated by the same schema.
- **Why:** R-5 asks for evidence with exact URL, observed date and excerpt or observation and separate fact and hypothesis fields; one schema for both formats keeps the rules in one place, and CSV stays flat for hand editing.

## A-3 · plan
- **Question:** How is the record validated, and where does the schema live?
- **Answer:** Add the jsonschema dependency and ship cottonwood/schemas/research-record.schema.json (draft 2020-12) inside the package so it is found when installed; Python adds checks the schema cannot express: real and not-future dates (America/Denver), http(s) URL with a host, email and E.164 phone through cottonwood.normalize, exact non-negative plain decimals, and the referred_by lead. Errors read 'rejected record N[ (record_id)]: FIELD: RULE' with JSON-path fields like evidence[0].url and the jsonschema keyword (or our rule name) as RULE.
- **Why:** architecture.md decision 4 chooses jsonschema so the skill and the validator share one definition; packaging the schema avoids the earlier migrations-dir-not-packaged problem; R-6 asks for record, field and rule.

## A-4 · plan
- **Question:** Where are verified facts and evidence observations stored, given leads has only hypothesis and evidence only excerpt?
- **Answer:** Migration 004_prospects adds leads.verified_facts (JSON array text) and evidence.observation (TEXT); excerpt and observation stay separate columns.
- **Why:** R-5 keeps facts apart from hypotheses and allows excerpt or observation; plain columns (not activity payloads) can be cleared on a deletion request (R-35), following 003_inbound's precedent.

## A-5 · plan
- **Question:** Stage, activities and exit code for an import?
- **Answer:** New leads start at stage researched. Each created lead, and each matched lead that gains evidence, gets one imported activity (payload: file name, record number, record_id, created, new_evidence count; no personal data). An identical re-import writes no rows. Each rejected record writes one import_rejected activity (file, record, record_id, field, rule) with no lead. Each record is all-or-nothing in a savepoint. Exit 0 when nothing was rejected, else 1 after importing the valid records; file-level errors exit 1 and write nothing.
- **Why:** The weekly report already counts researched leads from imported activities and data-quality failures from import_rejected (weekly-report assumption 4); R-35 keeps personal data out of append-only payloads; architecture.md says exit 1 is a validation refusal.

## A-6 · plan
- **Question:** R-7 matching details: when is a record the same organization, contact, lead or evidence, and what happens to a matched suppressed contact?
- **Answer:** Organization: by normalized domain when the record has one (no match means a new organization even if a name matches), else by normalized name. Contact: not-deleted contact by normalized email, else by normalized name within the organization. Lead: same organization, type and property location (trimmed, case-insensitive, both empty match). Evidence: same lead, URL, observed date and excerpt or observation. Matched rows keep every stored value, including a matched contact's eligibility; differing incoming non-empty fields print 'record N: FIELD differs: stored X, incoming Y (kept stored)'. Records earlier in the same file count as stored.
- **Why:** R-7 states the keys and that a matched record keeps stored values; suppression is enforced again at set-eligibility and prepare-send (R-24), so an import never needs to change a stored row.

## A-7 · fix
- **Question:** F-testing-1 (medium, coverage) could not be proved red: the mutant run imports the installed unmutated package (known issue CCGE-063). Force it or file it?
- **Answer:** Filed as CCGE-102 instead of forcing the proof.
- **Why:** Same handling as CCGE-087 in weekly-report; a red-green proof is never skipped, and a failed fix below high is filed.
