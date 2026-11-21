# sir-target: tests/test_database_missing_error.py
"""One DatabaseMissingError shared by db and backup (F-maintainability-2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cottonwood import backup, db

ROOT = Path(__file__).resolve().parent.parent


def test_exactly_one_definition_in_the_package() -> None:
    hits = [
        f"{path.name}:{n}"
        for path in sorted((ROOT / "cottonwood").rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"^\s*class DatabaseMissingError\b", line)
    ]
    assert len(hits) == 1, hits
    assert hits[0].startswith("db.py:"), hits


def test_backup_and_connect_raise_the_same_class(tmp_path: Path) -> None:
    assert backup.DatabaseMissingError is db.DatabaseMissingError
    missing = tmp_path / "missing.db"
    with pytest.raises(db.DatabaseMissingError) as from_backup:
        backup.backup(missing, tmp_path)
    with pytest.raises(db.DatabaseMissingError) as from_connect:
        db.connect(missing)
    assert type(from_backup.value) is type(from_connect.value)
