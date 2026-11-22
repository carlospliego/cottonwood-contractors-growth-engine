# sir-target: tests/test_migration_numbered_000.py
"""A migration numbered 000 is refused by name: numbering starts at 001 (F-correctness-4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db


def test_a_migration_numbered_000_is_refused_by_name(tmp_path: Path) -> None:
    (tmp_path / "000_x.sql").write_text("CREATE TABLE t (id INTEGER);\n", encoding="utf-8")
    with pytest.raises(db.MigrationError) as caught:
        db.discover_migrations(tmp_path)
    assert "000_x.sql" in str(caught.value)
    assert "start at 001" in str(caught.value)


def test_000_is_refused_even_beside_a_valid_001(tmp_path: Path) -> None:
    (tmp_path / "000_x.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "001_y.sql").write_text("SELECT 1;\n", encoding="utf-8")
    with pytest.raises(db.MigrationError, match="000_x.sql"):
        db.discover_migrations(tmp_path)
