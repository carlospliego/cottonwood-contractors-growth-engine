# Assumptions — send-gate

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Where do the R-21 sender identity, postal address, opt-out line and ad identification come from, and what values ship?
- **Answer:** A new optional `sending:` section in config/pilot.yaml (sender_identity, postal_address, opt_out_line, ad_identification), shipped with every key commented out; prepare-send fails sender_identity/postal_address while they are empty and checks that the draft contains each configured value verbatim.
- **Why:** R-21 says the values are configured and that prepare-send refuses when sender identity or postal address is empty; the founder has not decided them (open questions), so the gate must stay closed until they are set.

## A-2 · plan
- **Question:** prepare-send must know which claims a draft uses, but the drafting skill (outreach-skill) is built later: which feature defines the draft claims list format?
- **Answer:** send-gate defines cottonwood/schemas/draft-claims.schema.json (a JSON array of {claim_id, status}) and its loader, since prepare-send consumes it; outreach-skill will write files in that format. prepare-send recomputes each claim's effective status and never trusts the status in the list.
- **Why:** The consumer must define and validate the contract it relies on; the architecture already names schemas/draft-claims.schema.json as the skill's output schema.

## A-3 · plan
- **Question:** R-22 says log-outreach records the recipient; should the recipient address be stored in the append-only activities table, and what exit code does a recorded gate violation return?
- **Answer:** No email is stored in activities: sent and gate_violation rows carry the lead's contact_id and recipient_matches (true/false); the send is always recorded, and a send with any violation also records a gate_violation and exits 1. An unset max evidence age fails prepare-send's evidence check.
- **Why:** Activities are append-only and cannot honor a deletion request (open R-35/R-17 question), so contact data stays in contacts and suppression, as suppress already does; exit 1 makes a violation impossible to miss while still recording what happened.
