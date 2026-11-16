"""The shipped config and claims carry the founder brief's answers of 2026-11-15 (CCGE-146)."""

from pathlib import Path

from cottonwood import claims, config

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://cottonwoodcontractors.com/"


def test_pilot_config_carries_the_brief_answers() -> None:
    cfg = config.load_config(ROOT / "config" / "pilot.yaml")
    assert cfg.review.max_evidence_age_days == 90
    assert cfg.sending.opt_out_line == (
        'Don\'t want to hear from us? Reply "unsubscribe" and we will never contact you again.'
    )
    assert cfg.sending.ad_identification == (
        "This is a business solicitation from Cottonwood Contractors."
    )
    assert cfg.sending.sender_identity == ""
    assert cfg.sending.postal_address == ""
    assert cfg.sending_blocked_by == "Founder: sender identity and business postal address"
    assert cfg.model_cost_cap_usd is None


def test_claims_follow_the_website_and_stay_unverified() -> None:
    shipped = claims.load_claims(ROOT / "config" / "claims.yaml")
    assert [claim.id for claim in shipped] == [
        "fashion-place-attribution",
        "service-area",
        "license-classification",
        "insurance-bonding",
        "prior-company-experience",
        "website-projects",
    ]
    for claim in shipped:
        assert claim.status == "unverified"
        assert claim.verified_by is None
        assert claim.verified_at is None
    by_id = {claim.id: claim for claim in shipped}
    area = by_id["service-area"].text
    assert "Salt Lake County" in area
    for other in ("Davis", "Weber", "Utah County", "Utah,"):
        assert other not in area
    projects = by_id["website-projects"].text
    for name in (
        "Coffered Ceiling Kitchen",
        "Spa-Inspired Primary Bathroom",
        "Primary Bathroom in Lehi",
        "Lower-Level Family Room",
        "Open-Concept Great Room",
    ):
        assert name in projects
    for claim_id in ("fashion-place-attribution", "service-area", "website-projects"):
        assert SITE in by_id[claim_id].evidence
