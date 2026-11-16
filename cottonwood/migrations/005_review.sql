-- 005_review: checklist answers on researched leads (R-13). No BEGIN/COMMIT: the runner wraps
-- this file. leads.checklist is a JSON object of item key -> yes/no/unknown, NULL when absent.

ALTER TABLE leads ADD COLUMN checklist TEXT;
