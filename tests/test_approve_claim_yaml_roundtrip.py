# sir-target: tests/test_approve_claim_yaml_roundtrip.py
"""The verified_by and verified_at that 'approve claim' prints read back exactly (R-19).

F-correctness-4: the line printed 'verified_by: NAME' bare, so a name YAML reads as something
else ('Yes' a boolean, '123' a number, 'Smith: Jo' a mapping) pasted into the claims file no
longer matched its claim_verified activity, and the claim stayed unverified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import claims, config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
MARKER = "; mark it verified in config/claims.yaml with verified_by: "
DATE_SEP = " and verified_at: "


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _claims_file(tmp_path: Path, name: str, status: str, verified: str = "") -> Path:
    path = tmp_path / name
    path.write_text(
        "claims:\n"
        "  - id: service-area\n"
        "    text: Serves the Salt Lake valley.\n"
        f"    status: {status}\n"
        "    evidence: Founder email.\n" + verified,
        encoding="utf-8",
    )
    return path


def _printed_values(out: str) -> tuple[str, str]:
    """The verified_by and verified_at text exactly as approve claim printed them."""
    line = out.removesuffix("\n")
    assert "\n" not in line
    _, _, tail = line.partition(MARKER)
    verified_by, _, verified_at = tail.rpartition(DATE_SEP)
    return verified_by, verified_at


@pytest.mark.parametrize(
    "approver",
    [
        "Founder",
        "Yes",
        "123",
        "Smith: Jo",
        "Jo #2",
        "null",
        "~",
        "2026-11-30",
        "O'Brien",
        'Toni "T" Smith',
        "- Jo",
        "[Jo]",
        "Zoë",
    ],
)
def test_the_printed_verified_by_reads_back_as_the_approver(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], approver: str
) -> None:
    library = _claims_file(tmp_path, "claims.yaml", "unverified")
    capsys.readouterr()
    command = ["approve", "claim", "service-area", "--approver", approver, "--reference", "r"]
    assert main([*command, "--claims", str(library), "--db", str(db_path)]) == EXIT_OK
    verified_by, verified_at = _printed_values(capsys.readouterr().out)
    assert verified_at == "2026-11-30"

    marked = _claims_file(
        tmp_path,
        "marked.yaml",
        "verified",
        f"    verified_by: {verified_by}\n    verified_at: {verified_at}\n",
    )
    assert main(["claims", "--claims", str(marked), "--db", str(db_path)]) == EXIT_OK
    assert capsys.readouterr().out == "service-area: verified\n"


def test_a_plain_name_is_still_printed_bare() -> None:
    # AC-2.3 of the approvals-and-claims spec prints 'verified_by: Founder' unquoted.
    assert claims.yaml_value("Founder") == "Founder"
    assert claims.yaml_value("Toni Smith") == "Toni Smith"


@pytest.mark.parametrize(
    ("name", "printed"),
    [("Yes", '"Yes"'), ("123", '"123"'), ("Smith: Jo", '"Smith: Jo"')],
)
def test_a_name_yaml_would_misread_is_double_quoted(name: str, printed: str) -> None:
    assert claims.yaml_value(name) == printed
