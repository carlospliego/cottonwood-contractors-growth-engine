-- 003_inbound: the inquirer's stated project scope (R-1). No BEGIN/COMMIT: the runner wraps this file.
-- A plain column, not an activity payload, so a deletion request can clear it (R-35).

ALTER TABLE leads ADD COLUMN project_scope TEXT;
