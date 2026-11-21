"""Tests for the migrations runner and the migrate command."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

LATEST_VERSION = len(db.discover_migrations())


def _version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _tables(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            " ORDER BY name"
        ).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def test_help_lists_migrate(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == EXIT_OK
    assert "migrate" in capsys.readouterr().out


CORE_TABLES = [
    "activities",
    "agent_runs",
    "contacts",
    "evidence",
    "leads",
    "organizations",
    "suppression",
]


def test_migrate_creates_the_core_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "new.db"
    assert not path.exists()

    assert main(["migrate", "--db", str(path)]) == EXIT_OK

    assert path.is_file()
    assert _version(path) == LATEST_VERSION
    assert _tables(path) == CORE_TABLES
    assert f"at version {LATEST_VERSION} (applied {LATEST_VERSION})" in capsys.readouterr().out


def test_package_ships_baseline_core_then_inbound_migration() -> None:
    migrations = db.discover_migrations()
    assert [m.path.name for m in migrations] == [
        "001_baseline.sql",
        "002_core.sql",
        "003_inbound.sql",
        "004_prospects.sql",
        "005_review.sql",
        "006_contact_address.sql",
    ]


def test_second_migrate_applies_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "twice.db"
    assert main(["migrate", "--db", str(path)]) == EXIT_OK
    capsys.readouterr()

    assert main(["migrate", "--db", str(path)]) == EXIT_OK

    assert _version(path) == LATEST_VERSION
    assert f"at version {LATEST_VERSION} (applied 0)" in capsys.readouterr().out


def test_migrations_apply_in_numeric_order(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    # 002 depends on the table 001 creates, so applying out of order would fail.
    (migrations / "002_add_row.sql").write_text("INSERT INTO log (step) VALUES ('second');\n")
    (migrations / "001_create.sql").write_text(
        "CREATE TABLE log (id INTEGER PRIMARY KEY, step TEXT NOT NULL);\n"
        "INSERT INTO log (step) VALUES ('first');\n"
    )
    path = tmp_path / "ordered.db"

    result = db.migrate(path, migrations)

    assert (result.from_version, result.to_version) == (0, 2)
    assert [m.number for m in result.applied] == [1, 2]
    assert _version(path) == 2
    conn = sqlite3.connect(path)
    try:
        steps = [row[0] for row in conn.execute("SELECT step FROM log ORDER BY id")]
    finally:
        conn.close()
    assert steps == ["first", "second"]


def test_migration_at_or_below_current_version_is_not_applied(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_create.sql").write_text("CREATE TABLE log (step TEXT);\n")
    (migrations / "002_insert.sql").write_text("INSERT INTO log VALUES ('two');\n")
    path = tmp_path / "partial.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE log (step TEXT)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    result = db.migrate(path, migrations)

    # 001 would fail with "table log already exists" if it ran again.
    assert [m.number for m in result.applied] == [2]
    assert _version(path) == 2


def test_failed_migration_rolls_back_and_keeps_version(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_create.sql").write_text("CREATE TABLE ok (id INTEGER);\n")
    (migrations / "002_broken.sql").write_text("CREATE TABLE half (id INTEGER);\nNOT VALID SQL;\n")
    path = tmp_path / "broken.db"

    with pytest.raises(db.MigrationError, match="002_broken.sql"):
        db.migrate(path, migrations)

    assert _version(path) == 1
    assert _tables(path) == ["ok"]


def test_bad_migration_file_name_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_short.sql").write_text("SELECT 1;\n")

    with pytest.raises(db.MigrationError, match="1_short.sql"):
        db.discover_migrations(migrations)


def test_duplicate_migration_number_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_a.sql").write_text("SELECT 1;\n")
    (migrations / "001_b.sql").write_text("SELECT 1;\n")

    with pytest.raises(db.MigrationError, match="001"):
        db.discover_migrations(migrations)


def test_missing_folder_exits_1_names_it_and_creates_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "no-such-folder"
    path = folder / "x.db"

    code = main(["migrate", "--db", str(path)])

    assert code == EXIT_REFUSED
    assert str(folder) in capsys.readouterr().err
    assert not path.exists()
    assert not folder.exists()


def test_env_var_sets_the_database_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "from-env.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    monkeypatch.chdir(tmp_path)

    assert main(["migrate"]) == EXIT_OK

    assert path.is_file()
    assert _version(path) == LATEST_VERSION
    assert not (tmp_path / "data").exists()
    assert str(path) in capsys.readouterr().out


def test_default_path_is_data_cottonwood_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(db.DB_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    assert main(["migrate"]) == EXIT_OK

    assert (tmp_path / "data" / "cottonwood.db").is_file()
    assert _version(tmp_path / "data" / "cottonwood.db") == LATEST_VERSION


def test_db_flag_overrides_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env.db"
    flag_path = tmp_path / "flag.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(env_path))

    assert main(["migrate", "--db", str(flag_path)]) == EXIT_OK

    assert flag_path.is_file()
    assert not env_path.exists()
