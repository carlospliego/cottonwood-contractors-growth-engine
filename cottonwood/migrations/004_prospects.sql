-- 004_prospects: researched facts and evidence observations (R-5). No BEGIN/COMMIT: the runner
-- wraps this file. Plain columns, not activity payloads, so a deletion request can clear them
-- (R-35).

-- The record's verified facts, kept apart from leads.hypothesis, as a JSON array of strings.
ALTER TABLE leads ADD COLUMN verified_facts TEXT;

-- What was observed at the source when there is no quotable excerpt.
ALTER TABLE evidence ADD COLUMN observation TEXT;
