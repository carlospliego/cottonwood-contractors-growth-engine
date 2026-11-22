# sir-target: tests/test_migration_transaction_docs.py
"""Migration authors are told the runner owns the transaction (F-maintainability-4)."""

from __future__ import annotations

from cottonwood import db


def _header(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if not line.startswith("--"):
            break
        lines.append(line)
    return " ".join(line.removeprefix("--").strip() for line in lines)


def test_the_baseline_header_says_no_transaction_control() -> None:
    header = _header((db.MIGRATIONS_DIR / "001_baseline.sql").read_text(encoding="utf-8"))
    assert "must not contain BEGIN, COMMIT or ROLLBACK" in header


def test_the_apply_docstring_says_no_transaction_control() -> None:
    doc = " ".join((db._apply.__doc__ or "").split())
    assert "must not contain BEGIN, COMMIT or ROLLBACK" in doc


def test_the_baseline_still_migrates() -> None:
    assert db.discover_migrations()[0].path.name == "001_baseline.sql"
