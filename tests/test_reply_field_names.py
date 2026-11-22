# sir-target: tests/test_reply_field_names.py
"""No Reply field shares a name with a module send.py imports.

F-maintainability-2 (review 20261115-191126): Reply.eligibility had the same name as the
imported eligibility module, so inside the class the annotation and the field read alike.
"""

from __future__ import annotations

import dataclasses

from cottonwood import eligibility, send


def test_reply_has_no_field_named_eligibility() -> None:
    names = {field.name for field in dataclasses.fields(send.Reply)}
    assert "eligibility" not in names
    assert "eligibility_change" in names


def test_the_eligibility_change_is_still_printed() -> None:
    change = eligibility.EligibilityChange(7, "eligible", "ineligible", 12)
    reply = send.Reply(3, "opt_out", 11, suppressed_contact=7, eligibility_change=change)
    assert reply.lines() == [
        "reply recorded: lead 3 opt_out (activity 11)",
        "suppressed: contact 7",
        change.line(),
    ]
