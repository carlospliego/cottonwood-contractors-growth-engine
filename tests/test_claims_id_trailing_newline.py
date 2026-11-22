# sir-target: tests/test_claims_id_trailing_newline.py
"""A claim id with a trailing newline is refused when the claims file loads (R-19).

F-correctness-1: the id pattern ended in '$', which also matches before one trailing newline,
so a YAML block scalar id 'service-area\\n' loaded, yet 'approve claim service-area' could
never match it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import claims, config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"

ENTRY_TAIL = """\
    text: Serves the Salt Lake valley.
    status: unverified
    evidence: Founder email.
"""


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


def _claims_file(tmp_path: Path, id_lines: str) -> Path:
    path = tmp_path / "claims.yaml"
    path.write_text("claims:\n" + id_lines + ENTRY_TAIL, encoding="utf-8")
    return path


def _claims(db_path: Path, path: Path) -> int:
    return main(["claims", "--claims", str(path), "--db", str(db_path)])


def test_a_block_scalar_id_ending_in_a_newline_is_refused(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # '|' keeps the final newline, so the id is 'service-area\n'.
    path = _claims_file(tmp_path, "  - id: |\n      service-area\n")
    capsys.readouterr()
    assert _claims(db_path, path) == EXIT_REFUSED
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: ")
    assert "claims[1]" in lines[0]  # the first claim, counted from 1
    assert "id: " in lines[0]
    assert "'service-area\\n'" in lines[0]


def test_the_plain_id_still_loads(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _claims_file(tmp_path, "  - id: service-area\n")
    capsys.readouterr()
    assert _claims(db_path, path) == EXIT_OK
    assert "service-area" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("claim_id", "loads"),
    [
        ("service-area", True),
        ("service-area\n", False),
        ("service-area \n", False),
        ("service-area\t", False),
        (" service-area", False),
    ],
)
def test_the_id_pattern_must_match_the_whole_id(claim_id: str, loads: bool) -> None:
    assert (claims._ID.fullmatch(claim_id) is not None) is loads
