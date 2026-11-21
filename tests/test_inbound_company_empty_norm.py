# sir-target: tests/test_inbound_company_empty_norm.py
"""A company that normalizes to '' is refused, not merged into one org (F-correctness-4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, inbound


def _raw(company: str | None) -> inbound.RawInquiry:
    return inbound.RawInquiry(
        channel="form",
        received="2026-11-16 09:30",
        segment="commercial",
        name="Pat Lee",
        email="pat@example.com",
        company=company,
    )


@pytest.mark.parametrize("company", ["!!!", "—", "& / -", "'"])
def test_a_company_with_no_letters_or_digits_is_refused(company: str) -> None:
    with pytest.raises(inbound.InquiryError, match="letter or digit") as caught:
        inbound.validate(_raw(company))
    assert caught.value.field == "company"


def test_a_blank_company_is_still_not_supplied() -> None:
    assert inbound.validate(_raw("   ")).company is None


def test_real_company_names_still_share_an_organization(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        first = inbound.log_inquiry(conn, inbound.validate(_raw("Acme Builders")))
        second = inbound.log_inquiry(conn, inbound.validate(_raw("ACME builders!")))
        orgs = {
            int(row[0])
            for row in conn.execute(
                "SELECT organization_id FROM leads WHERE id IN (?, ?)", (first, second)
            )
        }
    finally:
        conn.close()
    assert len(orgs) == 1
