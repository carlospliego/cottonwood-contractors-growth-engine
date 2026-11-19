-- 006_contact_address: a contact's public postal address, so a researched prospect can be
-- reached by mail or a visit when no email or phone is published. No BEGIN/COMMIT: the runner
-- wraps this file. Nullable, like the other contact fields a deletion request clears (R-35).

ALTER TABLE contacts ADD COLUMN address TEXT;
