# sir-target: tests/test_backup_failure.py
"""Tests for the failed-backup cleanup path (F-testing-1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db
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


def test_backup_to_a_read_only_folder_exits_1_with_an_error_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CCGE-014: an OSError while claiming the backup file is an error line, not a traceback."""
    source = tmp_path / "cottonwood.db"
    db.migrate(source)
    dest = tmp_path / "read-only"
    dest.mkdir()
    dest.chmod(0o500)
    try:
        code = main(["backup", "--db", str(source), "--to", str(dest)])
    finally:
        dest.chmod(0o700)

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    error_lines = [line for line in err.splitlines() if line.startswith("error:")]
    assert len(error_lines) == 1
    assert str(dest) in error_lines[0]
    assert "Traceback" not in err
    assert list(dest.iterdir()) == []
