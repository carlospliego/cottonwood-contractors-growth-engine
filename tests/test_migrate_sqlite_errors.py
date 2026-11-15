# sir-target: tests/test_migrate_sqlite_errors.py
"""Regression: SQLite errors while opening or reading the database exit 1, not a traceback."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood.cli import EXIT_REFUSED, main


def test_non_sqlite_file_exits_1_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "not-a-db.db"
    garbage = b"this is plainly not a SQLite database file, just some text.\n" * 20
    path.write_bytes(garbage)

    assert main(["migrate", "--db", str(path)]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert str(path) in err
    assert path.read_bytes() == garbage


def test_directory_as_db_path_exits_1_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "a-directory"
    path.mkdir()

    assert main(["migrate", "--db", str(path)]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert str(path) in err
