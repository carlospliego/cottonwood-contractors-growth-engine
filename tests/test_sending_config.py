"""Tests for the sending section of the pilot config (R-21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config

ROOT = Path(__file__).resolve().parent.parent
FULL = (
    "sending:\n"
    '  sender_identity: "Cottonwood Contractors"\n'
    '  postal_address: "1 Main St, Sandy, UT 84070"\n'
    '  opt_out_line: "Reply STOP to opt out."\n'
    '  ad_identification: "Advertisement"\n'
)


def _load(tmp_path: Path, text: str) -> config.Config:
    path = tmp_path / "pilot.yaml"
    path.write_text(text, encoding="utf-8")
    return config.load_config(path)


def test_all_four_sending_values_load(tmp_path: Path) -> None:
    sending = _load(tmp_path, FULL).sending
    assert sending == config.SendingConfig(
        sender_identity="Cottonwood Contractors",
        postal_address="1 Main St, Sandy, UT 84070",
        opt_out_line="Reply STOP to opt out.",
        ad_identification="Advertisement",
    )


def test_a_missing_section_loads_as_not_configured(tmp_path: Path) -> None:
    assert _load(tmp_path, "paths:\n  backup_dir: data/backups\n").sending == config.SendingConfig()


def test_missing_keys_load_as_empty(tmp_path: Path) -> None:
    sending = _load(tmp_path, 'sending:\n  sender_identity: "Cottonwood"\n').sending
    assert sending.sender_identity == "Cottonwood"
    assert sending.postal_address == ""
    assert sending.opt_out_line == ""
    assert sending.ad_identification == ""


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("sending: [1]\n", "sending"),
        ("sending: {postal_address: 12}\n", "sending.postal_address"),
        ("sending: {opt_out_line: [a]}\n", "sending.opt_out_line"),
    ],
)
def test_bad_sending_values_are_refused(tmp_path: Path, text: str, needle: str) -> None:
    with pytest.raises(config.ConfigError) as excinfo:
        _load(tmp_path, text)
    assert needle in str(excinfo.value)


def test_the_shipped_config_documents_sending_but_leaves_it_unset() -> None:
    path = ROOT / "config" / "pilot.yaml"
    text = path.read_text(encoding="utf-8")
    assert "# sending:" in text
    assert "\nsending:" not in text
    assert config.load_config(path).sending == config.SendingConfig()
