# sir-target: tests/test_backup_failure.py
"""Tests for the failed-backup cleanup path (F-testing-1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood.cli import EXIT_REFUSED, main


def test_backup_of_non_sqlite_file_exits_1_and_leaves_no_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "not-a-db.db"
    source.write_bytes(b"this is plain text, not a SQLite database\n" * 4)
    original = source.read_bytes()
    dest = tmp_path / "backups"
    dest.mkdir()

    code = main(["backup", "--db", str(source), "--to", str(dest)])

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert f"backup of {source} failed" in err
    assert list(dest.iterdir()) == []
    assert source.read_bytes() == original
