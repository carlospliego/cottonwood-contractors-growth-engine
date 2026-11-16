"""Tests for the draft claims list contract (R-20, R-21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cottonwood import draft_claims

ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "1-1.claims.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_schema_ships_with_the_package() -> None:
    assert (ROOT / "cottonwood" / "schemas" / "draft-claims.schema.json").is_file()
    assert draft_claims.schema()["type"] == "array"


def test_a_valid_list_returns_its_claim_ids_in_order(tmp_path: Path) -> None:
    items = [
        {"claim_id": "service-area", "status": "verified"},
        {"claim_id": "licensed", "status": "unverified"},
    ]
    path = _write(tmp_path, json.dumps(items))
    assert draft_claims.load_draft_claims(path) == ("service-area", "licensed")


def test_an_empty_list_uses_no_claims(tmp_path: Path) -> None:
    assert draft_claims.load_draft_claims(_write(tmp_path, "[]")) == ()


def test_a_missing_file_is_refused_naming_it(tmp_path: Path) -> None:
    path = tmp_path / "missing.claims.json"
    with pytest.raises(draft_claims.DraftClaimsError) as excinfo:
        draft_claims.load_draft_claims(path)
    assert str(path) in str(excinfo.value)


@pytest.mark.parametrize(
    "text",
    [
        "{not json",
        "{}",
        json.dumps([{"claim_id": "Service_Area", "status": "verified"}]),
        json.dumps([{"claim_id": "a", "status": "maybe"}]),
        json.dumps([{"claim_id": "a"}]),
        json.dumps([{"claim_id": "a", "status": "verified", "extra": 1}]),
    ],
)
def test_an_invalid_list_is_refused_naming_the_file(tmp_path: Path, text: str) -> None:
    path = _write(tmp_path, text)
    with pytest.raises(draft_claims.DraftClaimsError) as excinfo:
        draft_claims.load_draft_claims(path)
    assert str(path) in str(excinfo.value)


def test_the_default_claims_list_sits_next_to_the_draft() -> None:
    assert draft_claims.claims_list_path(Path("out/drafts/1-1.md")) == Path(
        "out/drafts/1-1.claims.json"
    )
