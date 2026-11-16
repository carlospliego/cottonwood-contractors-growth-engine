# sir-target: tests/test_prepare_send_cleanup.py
"""prepare-send: a failed output write or commit leaves no sendable file and no record."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
SENDER = "Cottonwood Contractors"
POSTAL = "1 Main St, Sandy, UT 84070"
OPT_OUT = "Reply STOP to opt out."
AD = "Advertisement"
REF = "email 2026-11-29 Re: outreach"
BODY = f"{AD}\n\nHello Pat,\n\nA short note.\n\n{SENDER}\n{POSTAL}\n{OPT_OUT}\n"


class FailingCommit:
    """A connection proxy whose commit fails."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def commit(self) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    def __getattr__(self, name: str) -> object:
        return getattr(self._conn, name)


class Env:
    def __init__(self, tmp: Path) -> None:
        self.db = tmp / "cottonwood.db"
        self.config = tmp / "pilot.yaml"
        self.claims = tmp / "claims.yaml"
        self.draft = tmp / "1-1.md"
        self.out = tmp / "send"

    def run(self, *args: str) -> int:
        return main([*args, "--db", str(self.db)])

    def prepare(self) -> int:
        return self.run(
            "prepare-send",
            "1",
            str(self.draft),
            "--claims",
            str(self.claims),
            "--out",
            str(self.out),
            "--config",
            str(self.config),
        )

    def sql(self, statement: str, params: tuple[object, ...] = ()) -> None:
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(statement, params)
            conn.commit()
        finally:
            conn.close()

    def prepared(self) -> int:
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM activities WHERE type = 'draft_prepared'"
            ).fetchone()
        finally:
            conn.close()
        return int(row[0])


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)
    e = Env(tmp_path)
    lines = ["paths:", "  backup_dir: data/backups", "review:", "  max_evidence_age_days: 30"]
    lines.append("sending:")
    sending = {
        "sender_identity": SENDER,
        "postal_address": POSTAL,
        "opt_out_line": OPT_OUT,
        "ad_identification": AD,
    }
    lines += [f"  {key}: {json.dumps(value)}" for key, value in sending.items()]
    e.config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(e.config))
    db.migrate(e.db)
    e.sql(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', 'pat@firm.example.com',"
        " 'eligible')"
    )
    e.sql(
        "INSERT INTO leads (id, type, stage, contact_id)"
        " VALUES (1, 'direct_candidate', 'researched', 1)"
    )
    e.sql(
        "INSERT INTO evidence (lead_id, url, observed_at, kind)"
        " VALUES (1, 'https://firm.example.com/news', '2026-11-20', 'fact')"
    )
    e.draft.write_text(BODY, encoding="utf-8")
    entry = {
        "id": "service-area",
        "text": "Serves four counties.",
        "status": "verified",
        "evidence": "Founder email.",
        "verified_by": "Founder",
        "verified_at": "2026-11-30",
    }
    e.claims.write_text(json.dumps({"claims": [entry]}), encoding="utf-8")
    claims_list = tmp_path / "1-1.claims.json"
    claims_list.write_text(
        json.dumps([{"claim_id": "service-area", "status": "verified"}]), encoding="utf-8"
    )
    assert e.run("approve", "lead", "1", "--approver", "Founder", "--reference", REF) == EXIT_OK
    draft_args = ["approve", "draft", str(e.draft), "--lead", "1", "--approver", "Founder"]
    assert e.run(*draft_args, "--reference", REF) == EXIT_OK
    claim_args = ["approve", "claim", "service-area", "--approver", "Founder"]
    assert e.run(*claim_args, "--reference", REF, "--claims", str(e.claims)) == EXIT_OK
    return e


def test_the_ready_draft_is_prepared_when_nothing_fails(env: Env) -> None:
    assert env.prepare() == EXIT_OK
    assert (env.out / env.draft.name).read_text(encoding="utf-8") == BODY
    assert env.prepared() == 1


def test_a_failed_commit_removes_the_sendable_file_and_the_record(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_connect = db.connect
    monkeypatch.setattr(db, "connect", lambda *a, **k: FailingCommit(real_connect(*a, **k)))
    try:
        env.prepare()
    except sqlite3.Error:
        pass
    monkeypatch.undo()
    assert not (env.out / env.draft.name).exists()
    assert env.prepared() == 0


def test_an_unwritable_out_leaves_no_record(env: Env) -> None:
    env.out.write_text("not a directory", encoding="utf-8")
    try:
        env.prepare()
    except OSError:
        pass
    assert env.out.read_text(encoding="utf-8") == "not a directory"
    assert env.prepared() == 0
