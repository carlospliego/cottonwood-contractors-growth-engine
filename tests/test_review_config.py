"""Tests for the review block of config/pilot.yaml: checklists and max evidence age (R-10, R-13)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cottonwood import config

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config" / "pilot.yaml"
KEY = re.compile(r"[a-z][a-z0-9_]*")


def _load(tmp_path: Path, text: str) -> config.Config:
    path = tmp_path / "pilot.yaml"
    path.write_text(text, encoding="utf-8")
    return config.load_config(path)


def _refused(tmp_path: Path, text: str) -> str:
    with pytest.raises(config.ConfigError) as caught:
        _load(tmp_path, text)
    return str(caught.value)


GOOD_ITEM = "      - {key: fit, label: Fits}\n"


def test_repo_config_has_six_direct_and_five_relationship_items() -> None:
    loaded = config.load_config(REPO_CONFIG)
    checklists = loaded.review.checklists
    assert len(checklists["direct_candidate"]) == 6
    assert len(checklists["relationship_prospect"]) == 5
    for items in checklists.values():
        for item in items:
            assert item.key and KEY.fullmatch(item.key)
            assert item.label.strip()
    assert loaded.review.max_evidence_age_days is None


def test_missing_review_block_means_no_items_and_no_max_age(tmp_path: Path) -> None:
    loaded = _load(tmp_path, "paths:\n  backup_dir: data/backups\n")
    assert loaded.review.checklists == {"direct_candidate": (), "relationship_prospect": ()}
    assert loaded.review.max_evidence_age_days is None
    assert loaded.review.keys() == {
        "direct_candidate": frozenset(),
        "relationship_prospect": frozenset(),
    }


def test_items_and_max_age_load(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        "review:\n"
        "  max_evidence_age_days: 30\n"
        "  checklists:\n"
        "    direct_candidate:\n"
        "      - {key: direct_signal, label: ' Current signal '}\n"
        "      - {key: buyer_identified, label: Buyer known}\n",
    )
    items = loaded.review.checklists["direct_candidate"]
    assert [(item.key, item.label) for item in items] == [
        ("direct_signal", "Current signal"),
        ("buyer_identified", "Buyer known"),
    ]
    assert loaded.review.checklists["relationship_prospect"] == ()
    assert loaded.review.max_evidence_age_days == 30
    assert loaded.review.keys()["direct_candidate"] == {"direct_signal", "buyer_identified"}


def test_checklist_that_is_not_a_list_is_refused(tmp_path: Path) -> None:
    message = _refused(
        tmp_path, "review:\n  checklists:\n    direct_candidate: {key: fit, label: Fits}\n"
    )
    assert "review.checklists.direct_candidate" in message


def test_item_without_a_key_is_refused(tmp_path: Path) -> None:
    message = _refused(
        tmp_path,
        "review:\n  checklists:\n    direct_candidate:\n" + GOOD_ITEM + "      - {label: Fits}\n",
    )
    assert "review.checklists.direct_candidate[1].key" in message


def test_item_with_an_empty_label_is_refused(tmp_path: Path) -> None:
    message = _refused(
        tmp_path,
        "review:\n  checklists:\n    relationship_prospect:\n      - {key: fit, label: '  '}\n",
    )
    assert "review.checklists.relationship_prospect[0].label" in message


def test_key_not_lower_snake_case_is_refused(tmp_path: Path) -> None:
    message = _refused(
        tmp_path,
        "review:\n  checklists:\n    direct_candidate:\n"
        "      - {key: Direct-Signal, label: Signal}\n",
    )
    assert "review.checklists.direct_candidate[0].key" in message
    assert "Direct-Signal" in message


def test_duplicate_key_in_one_queue_is_refused(tmp_path: Path) -> None:
    message = _refused(
        tmp_path,
        "review:\n  checklists:\n    direct_candidate:\n" + GOOD_ITEM + GOOD_ITEM,
    )
    assert "review.checklists.direct_candidate[1].key" in message
    assert "duplicate" in message


def test_same_key_in_both_queues_is_allowed(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        "review:\n  checklists:\n    direct_candidate:\n"
        + GOOD_ITEM
        + "    relationship_prospect:\n"
        + GOOD_ITEM,
    )
    assert loaded.review.keys() == {
        "direct_candidate": frozenset({"fit"}),
        "relationship_prospect": frozenset({"fit"}),
    }


def test_unknown_queue_is_refused(tmp_path: Path) -> None:
    message = _refused(tmp_path, "review:\n  checklists:\n    inbound_inquiry:\n" + GOOD_ITEM)
    assert "review.checklists.inbound_inquiry" in message


@pytest.mark.parametrize("value", ["0", "-5", "ninety", "true", "1.5"])
def test_bad_max_evidence_age_is_refused(tmp_path: Path, value: str) -> None:
    message = _refused(tmp_path, f"review:\n  max_evidence_age_days: {value}\n")
    assert "review.max_evidence_age_days" in message
