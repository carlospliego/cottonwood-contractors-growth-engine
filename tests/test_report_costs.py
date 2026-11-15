"""Tests for report's costs and blocked-sending sections and their config keys (R-28-R-30)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
# The period ends mid-month so a run can start before it yet inside the end date's month.
PERIOD = ("--from", "2026-11-10", "--to", "2026-11-20")
BASE_CONFIG = "paths:\n  backup_dir: data/backups\n"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text(BASE_CONFIG, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path, config_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _set_config(config_path: Path, report_block: str) -> None:
    config_path.write_text(BASE_CONFIG + "report:\n" + report_block, encoding="utf-8")


def _run(db_path: Path, started_at: str, cost: str | None, estimated: int | None) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO agent_runs (skill, started_at, cost_usd, cost_estimated)"
            " VALUES ('prospect-research', ?, ?, ?)",
            (started_at, cost, estimated),
        )
        conn.commit()
    finally:
        conn.close()


def _cost(db_path: Path, amount: str, day: str, category: str, *args: str) -> None:
    code = main(
        ["log-cost", "--db", str(db_path), amount, "--date", day, "--category", category, *args]
    )
    assert code == EXIT_OK


def _report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *PERIOD]) == EXIT_OK
    return capsys.readouterr().out


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


def _seed_runs(db_path: Path) -> None:
    _run(db_path, "2026-11-12T17:00:00Z", "1.25", 0)  # in the period, observed
    _run(db_path, "2026-11-15T17:00:00Z", "0.50", 1)  # in the period, estimated
    _run(db_path, "2026-11-05T17:00:00Z", "2.00", 0)  # before the period, same month
    _run(db_path, "2026-10-28T17:00:00Z", "9.00", 0)  # previous month
    _run(db_path, "2026-11-25T17:00:00Z", "4.00", 0)  # after the period end
    _run(db_path, "2026-11-13T17:00:00Z", None, None)  # no cost recorded


# --- Model cost (AC-5.1) ----------------------------------------------------------------


def test_model_cost_with_cap(
    db_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_runs(db_path)
    _set_config(config_path, "  model_cost_cap_usd: 100\n")
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_MODEL_COST) == "1.75"
    assert _metric(text, report.LABEL_MODEL_OBSERVED) == "1.25"
    assert _metric(text, report.LABEL_MODEL_ESTIMATED) == "0.50"
    assert _metric(text, report.LABEL_MODEL_MTD) == "3.75 of 100.00 (96.25 remaining)"
    assert report.NO_CAP not in text


def test_model_cost_without_cap(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_runs(db_path)
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_MODEL_COST) == "1.75"
    assert _metric(text, report.LABEL_MODEL_MTD) == "3.75"
    assert "No model-cost cap configured" in text


def test_model_cost_over_cap(
    db_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_runs(db_path)
    _set_config(config_path, '  model_cost_cap_usd: "2.5"\n')
    assert _metric(_report(db_path, capsys), report.LABEL_MODEL_MTD) == (
        "3.75 of 2.50 (1.25 over cap)"
    )


def test_null_estimated_counts_observed_and_bad_cost_is_skipped(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(db_path, "2026-11-12T17:00:00Z", "1.10", None)
    _run(db_path, "2026-11-12T18:00:00Z", "n/a", 1)
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_MODEL_COST) == "1.10"
    assert _metric(text, report.LABEL_MODEL_OBSERVED) == "1.10"
    assert _metric(text, report.LABEL_MODEL_ESTIMATED) == "0.00"


def test_empty_database_prints_zero_costs(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = _report(db_path, capsys)
    assert "## Costs" in text
    for label in (
        report.LABEL_MODEL_COST,
        report.LABEL_MODEL_OBSERVED,
        report.LABEL_MODEL_ESTIMATED,
        report.LABEL_MODEL_MTD,
        report.LABEL_OTHER_COSTS,
        report.LABEL_OTHER_OBSERVED,
        report.LABEL_OTHER_ESTIMATED,
    ):
        assert _metric(text, label) == "0.00"
    assert "| Category |" not in text


# --- Other costs (AC-5.2) ---------------------------------------------------------------


def test_other_costs_total_split_and_categories(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _cost(db_path, "49.00", "2026-11-12", "Formspark plan")
    _cost(db_path, "10.00", "2026-11-14", "domain", "--estimated")
    _cost(db_path, "25.00", "2026-11-15", "domain")
    conn = db.connect(db_path)
    try:
        wrong = int(conn.execute("SELECT max(id) FROM activities").fetchone()[0])
    finally:
        conn.close()
    assert main(["log-cost", "--db", str(db_path), "--voids", str(wrong)]) == EXIT_OK
    _cost(db_path, "99.00", "2026-11-25", "domain")  # after the period
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_OTHER_COSTS) == "59.00"
    assert _metric(text, report.LABEL_OTHER_OBSERVED) == "49.00"
    assert _metric(text, report.LABEL_OTHER_ESTIMATED) == "10.00"
    costs = text.split("## Costs", 1)[1]
    assert "| Category | Amount (USD) |" in costs
    assert "| domain | 10.00 |" in costs
    assert "| formspark plan | 49.00 |" in costs


# --- Blocked sending (AC-5.3) -----------------------------------------------------------


def test_blocked_sending_section_quotes_the_question(
    db_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_config(config_path, '  sending_blocked_by: "Q3: which domain sends outreach"\n')
    text = _report(db_path, capsys)
    section = text.split(report.SENDING_BLOCKED_HEADING, 1)[1]
    assert report.SENDING_BLOCKED_INTRO in section
    assert "> Q3: which domain sends outreach" in section
    assert text.endswith("> Q3: which domain sends outreach\n")


@pytest.mark.parametrize("block", ["", '  sending_blocked_by: "   "\n', "  sending_blocked_by:\n"])
def test_no_blocked_text_when_unset_or_blank(
    db_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str], block: str
) -> None:
    if block:
        _set_config(config_path, block)
    text = _report(db_path, capsys)
    assert "Sending blocked" not in text
    assert "blocked" not in text.lower()


# --- Config keys (AC-5.1, AC-5.3, AC-4 of CCGE-082) ------------------------------------


@pytest.mark.parametrize(
    ("block", "key"),
    [
        ('  model_cost_cap_usd: "abc"\n', "report.model_cost_cap_usd"),
        ("  model_cost_cap_usd: -5\n", "report.model_cost_cap_usd"),
        ("  model_cost_cap_usd: true\n", "report.model_cost_cap_usd"),
        ("  model_cost_cap_usd: .inf\n", "report.model_cost_cap_usd"),
        ("  model_cost_cap_usd: [1]\n", "report.model_cost_cap_usd"),
        ("  sending_blocked_by: [a, b]\n", "report.sending_blocked_by"),
        ("  sending_blocked_by: 7\n", "report.sending_blocked_by"),
    ],
)
def test_bad_report_config_exits_1_naming_the_key(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    block: str,
    key: str,
) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(BASE_CONFIG + "report:\n" + block, encoding="utf-8")
    capsys.readouterr()
    code = main(["report", "--db", str(db_path), "--period", "7d", "--config", str(path)])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")
    assert key in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_report_not_a_mapping_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(BASE_CONFIG + "report: 5\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="report must be a mapping"):
        config.load_config(path)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("100", Decimal("100")), ("99.5", Decimal("99.5")), ('"12.34"', Decimal("12.34")), ("0", 0)],
)
def test_cap_values_accepted(tmp_path: Path, value: str, expected: Decimal) -> None:
    path = tmp_path / "ok.yaml"
    path.write_text(BASE_CONFIG + f"report:\n  model_cost_cap_usd: {value}\n", encoding="utf-8")
    assert config.load_config(path).model_cost_cap_usd == expected


def test_shipped_pilot_config_loads_with_keys_unset() -> None:
    cfg = config.load_config(Path(__file__).resolve().parents[1] / "config" / "pilot.yaml")
    assert cfg.model_cost_cap_usd is None
    assert cfg.sending_blocked_by is None


def test_blocked_by_is_stripped(tmp_path: Path) -> None:
    path = tmp_path / "ok.yaml"
    path.write_text(BASE_CONFIG + 'report:\n  sending_blocked_by: "  Q3  "\n', encoding="utf-8")
    assert config.load_config(path).sending_blocked_by == "Q3"


def test_money_formatting() -> None:
    assert report.money(Decimal("1.75")) == "1.75"
    assert report.money(Decimal("100")) == "100.00"
    assert report.money(Decimal("0.005")) == "0.01"
    assert report.money(Decimal("1E+3")) == "1000.00"
