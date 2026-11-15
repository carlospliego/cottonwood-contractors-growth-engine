-- 002_core: the seven core tables (architecture.md, Interfaces & data).
-- Timestamps are TEXT UTC ISO-8601 ending in Z. No BEGIN/COMMIT: the runner wraps this file.

CREATE TABLE organizations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    domain_norm TEXT,
    type TEXT,
    category TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX organizations_domain_norm_unique
    ON organizations (domain_norm) WHERE domain_norm IS NOT NULL;

-- Contact fields are nullable: a deletion request clears them and sets deleted_at (R-35).
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations (id),
    name TEXT,
    email TEXT,
    email_norm TEXT,
    phone_e164 TEXT,
    role TEXT,
    source_url TEXT,
    eligibility TEXT NOT NULL DEFAULT 'unknown'
        CHECK (eligibility IN ('eligible', 'ineligible', 'unknown')),
    deleted_at TEXT
);

CREATE INDEX contacts_email_norm ON contacts (email_norm);
CREATE INDEX contacts_phone_e164 ON contacts (phone_e164);

-- R-14: inbound and direct leads use the direct stages; relationship prospects their own.
CREATE TABLE leads (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL
        CHECK (type IN ('inbound_inquiry', 'direct_candidate', 'relationship_prospect')),
    organization_id INTEGER REFERENCES organizations (id),
    contact_id INTEGER REFERENCES contacts (id),
    stage TEXT NOT NULL,
    segment TEXT,
    channel TEXT,
    property_location TEXT,
    hypothesis TEXT,
    next_action TEXT,
    founder_time_h REAL,
    value_amount TEXT,
    value_basis TEXT,
    referred_by INTEGER REFERENCES leads (id),
    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0, 1)),
    received_at TEXT,
    CHECK (
        (type IN ('inbound_inquiry', 'direct_candidate') AND stage IN (
            'candidate', 'researched', 'contacted_or_replied', 'buyer_need_confirmed',
            'walkthrough', 'proposal', 'won', 'lost', 'closed_no_fit'
        ))
        OR (type = 'relationship_prospect' AND stage IN (
            'identified', 'researched', 'introduced', 'responded', 'active_relationship',
            'closed_no_fit'
        ))
    )
);

CREATE INDEX leads_type ON leads (type);

CREATE TABLE evidence (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads (id),
    url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    published_at TEXT,
    excerpt TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('fact', 'hypothesis')),
    source_status TEXT
);

-- Append-only (R-17): a correction is a new row whose voids_activity_id names the old one.
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER REFERENCES leads (id),
    contact_id INTEGER REFERENCES contacts (id),
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload)),
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    voids_activity_id INTEGER REFERENCES activities (id)
);

CREATE INDEX activities_lead_id ON activities (lead_id);

CREATE TRIGGER activities_no_update BEFORE UPDATE ON activities
BEGIN
    SELECT RAISE(ABORT, 'activities are append-only');
END;

CREATE TRIGGER activities_no_delete BEFORE DELETE ON activities
BEGIN
    SELECT RAISE(ABORT, 'activities are append-only');
END;

CREATE TABLE agent_runs (
    id INTEGER PRIMARY KEY,
    skill TEXT NOT NULL,
    skill_version TEXT,
    model TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    input_ref TEXT,
    output_ref TEXT,
    validation TEXT,
    tokens INTEGER,
    cost_usd TEXT,
    cost_source TEXT,
    cost_estimated INTEGER CHECK (cost_estimated IN (0, 1))
);

-- Suppression is never deleted or changed (R-24); it outlives contact deletion (R-35).
CREATE TABLE suppression (
    email_norm TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    source TEXT,
    added_at TEXT NOT NULL
);

CREATE TRIGGER suppression_no_update BEFORE UPDATE ON suppression
BEGIN
    SELECT RAISE(ABORT, 'suppression entries are never deleted or changed');
END;

CREATE TRIGGER suppression_no_delete BEFORE DELETE ON suppression
BEGIN
    SELECT RAISE(ABORT, 'suppression entries are never deleted or changed');
END;
