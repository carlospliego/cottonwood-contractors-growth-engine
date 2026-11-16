# Assumptions — outreach-skill

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** How does the prepare-outreach skill get its lead data, and does the export include the contact's email address?
- **Answer:** The developer runs `cottonwood review --lead ID --json --out out/leads/ID.json` and the skill reads that file (Read scoped to out/leads/**); the export omits the email address and carries the contact's id, name, role, eligibility and a suppressed flag.
- **Why:** Skills hold no credentials and have no shell (architecture decision 6, R-27); the draft body needs no address because the founder sends from their own client, and keeping addresses out of skill inputs limits contact-data spread (R-35).

## A-2 · plan
- **Question:** What does `review --lead ID --json` do for a suppressed contact or a lead without a contact email?
- **Answer:** It still exits 0 and exports the lead with draftable false and blocked_by naming suppressed or no_contact_email; the skill writes nothing when draftable is false, and prepare-send remains the enforcing gate.
- **Why:** R-20 makes the skill skip suppressed contacts; exporting the reason lets the skill and the developer see why nothing was drafted, while the deterministic refusal stays in prepare-send (R-21).
