"""Tests for the config loader and the backup command."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cottonwood import backup, config, db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-11-15T10:00:00Z"
BACKUP_NAME = re.compile(r"cottonwood-\d{8}T\d{6}Z(-\d+)?\.db")
REPO_ROOT = Path(__file__).resolve().parent.parent


def _migrated_db(tmp_path: Path) -> Path:
    path = tmp_path / "live.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        conn.execute(
            "INSERT INTO suppression (email_norm, reason, source, added_at)"
            " VALUES ('jane@example.com', 'opt_out', 'reply', ?)",
            (NOW,),
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _written_path(out: str) -> Path:
    match = re.fullmatch(r"backup written: (.+)\n", out)
    assert match is not None, out
    return Path(match.group(1))


def _version_and_suppression(path: Path) -> tuple[int, list[str]]:
    conn = sqlite3.connect(path)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        emails = [str(row[0]) for row in conn.execute("SELECT email_norm FROM suppression")]
        return version, emails
    finally:
        conn.close()


def test_backup_copies_schema_and_rows(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _migrated_db(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()

    code = main(["backup", "--db", str(source), "--to", str(dest)])

    assert code == EXIT_OK
    written = _written_path(capsys.readouterr().out)
    assert written.parent == dest
    assert BACKUP_NAME.fullmatch(written.name)
    assert _version_and_suppression(written) == (4, ["jane@example.com"])


def test_backup_to_missing_folder_exits_1_and_creates_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _migrated_db(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    missing = tmp_path / "no-such-folder"

    code = main(["backup", "--db", str(source), "--to", str(missing)])

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert f"backup folder does not exist: {missing}" in err
    assert not missing.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_backup_of_missing_database_exits_1_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    missing = tmp_path / "absent.db"

    code = main(["backup", "--db", str(missing), "--to", str(dest)])

    assert code == EXIT_REFUSED
    assert f"database does not exist: {missing}" in capsys.readouterr().err
    assert not missing.exists()
    assert list(dest.iterdir()) == []


def test_without_to_the_folder_comes_from_cottonwood_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _migrated_db(tmp_path)
    dest = tmp_path / "from-config"
    dest.mkdir()
    config_file = tmp_path / "pilot.yaml"
    config_file.write_text(f"paths:\n  backup_dir: {dest}\nother: ignored\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(config_file))
    monkeypatch.chdir(tmp_path)

    code = main(["backup", "--db", str(source)])

    assert code == EXIT_OK
    written = _written_path(capsys.readouterr().out)
    assert written.parent == dest
    assert _version_and_suppression(written) == (4, ["jane@example.com"])


def test_config_flag_beats_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _migrated_db(tmp_path)
    flag_dest = tmp_path / "flag"
    flag_dest.mkdir()
    flag_file = tmp_path / "flag.yaml"
    flag_file.write_text(f"paths:\n  backup_dir: {flag_dest}\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(tmp_path / "missing.yaml"))

    code = main(["backup", "--db", str(source), "--config", str(flag_file)])

    assert code == EXIT_OK
    assert _written_path(capsys.readouterr().out).parent == flag_dest


def test_missing_config_without_to_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _migrated_db(tmp_path)
    missing = tmp_path / "none.yaml"
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(missing))

    assert main(["backup", "--db", str(source)]) == EXIT_REFUSED
    assert f"config file does not exist: {missing}" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("paths: [unclosed\n", "not valid YAML"),
        ("- a list\n", "must hold a mapping"),
        ("paths: data/backups\n", "paths must be a mapping"),
        ("paths:\n  backup_dir: 5\n", "backup_dir must be a non-empty string"),
    ],
)
def test_invalid_config_raises_config_error(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(config.ConfigError, match=message):
        config.load_config(path)


def test_two_backups_in_the_same_second_get_distinct_names(tmp_path: Path) -> None:
    source = _migrated_db(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()

    def frozen() -> datetime:
        return datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC)

    first = backup.backup(source, dest, now=frozen)
    second = backup.backup(source, dest, now=frozen)
    third = backup.backup(source, dest, now=frozen)

    assert first.name == "cottonwood-20261115T100000Z.db"
    assert second.name == "cottonwood-20261115T100000Z-2.db"
    assert third.name == "cottonwood-20261115T100000Z-3.db"
    assert sorted(p.name for p in dest.iterdir()) == sorted([first.name, second.name, third.name])
    for path in (first, second, third):
        assert _version_and_suppression(path) == (4, ["jane@example.com"])


def test_shipped_pilot_config_sets_backup_dir() -> None:
    loaded = config.load_config(REPO_ROOT / "config" / "pilot.yaml")
    assert loaded.backup_dir == Path("data") / "backups"


def test_help_lists_backup(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == EXIT_OK
    assert "backup" in capsys.readouterr().out
