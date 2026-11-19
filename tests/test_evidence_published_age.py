"""Evidence age uses the publication date when known (CCGE-149, R-10).

Synthetic fixtures only: example.com URLs, '(TEST)' contact. Today is Denver 2026-11-30.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from test_prepare_send import FULL_SENDING, Setup, _payload, fixed_now, ready  # noqa: F401

from cottonwood.cli import EXIT_OK

TODAY = date(2026, 11, 30)  # Denver date of NOW in test_prepare_send


def _days_ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def _set_only_evidence(setup: Setup, observed: str, published: str | None) -> None:
    setup.sql("DELETE FROM evidence")
    setup.sql(
        "INSERT INTO evidence (lead_id, url, observed_at, published_at, kind)"
        " VALUES (1, 'https://firm.example.com/news', ?, ?, 'fact')",
        (observed, published),
    )


def _evidence_refusals(setup: Setup, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """Run prepare-send; return the 'refused: evidence:' lines and check the activity agrees."""
    capsys.readouterr()
    setup.prepare()
    lines = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("refused: evidence:")
    ]
    refused = setup.activities("prepare_refused")
    checks = _payload(refused[-1])["checks"] if refused else []
    assert ("evidence" in checks) == bool(lines)  # type: ignore[operator]
    return lines


def _review_row(setup: Setup, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """The cells of lead 1's row in the review's direct-candidate table."""
    capsys.readouterr()
    assert setup.run("review", "--config", str(setup.config)) == EXIT_OK
    out = capsys.readouterr().out
    section = out.split("## Direct candidates", 1)[1].split("\n## ", 1)[0]
    [row] = [line for line in section.splitlines() if line.startswith("| 1 |")]
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


# --- AC 1: published 120 days ago, observed today → prepare-send refuses ----------------


def test_old_publication_read_today_is_refused(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready.write_config(FULL_SENDING, max_age=90)
    published = _days_ago(120)
    _set_only_evidence(ready, observed=TODAY.isoformat(), published=published)

    [line] = _evidence_refusals(ready, capsys)

    assert published in line
    assert line == f"refused: evidence: newest evidence published {published} is older than 90 days"


# --- AC 2: review shows age 120, flagged over 90 ----------------------------------------


def test_review_age_counts_from_publication(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready.write_config(FULL_SENDING, max_age=90)
    _set_only_evidence(ready, observed=TODAY.isoformat(), published=_days_ago(120))

    cells = _review_row(ready, capsys)

    assert "120 (over 90)" in cells


# --- AC 3: no published date → falls back to observed today -----------------------------


def test_without_publication_date_observed_date_is_used(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready.write_config(FULL_SENDING, max_age=90)
    _set_only_evidence(ready, observed=TODAY.isoformat(), published=None)

    cells = _review_row(ready, capsys)
    assert "https://firm.example.com/news" in cells
    assert cells[cells.index("https://firm.example.com/news") + 1] == "0"
    assert _evidence_refusals(ready, capsys) == []


# --- AC 4: newest by publication date wins -----------------------------------------------


def test_newest_publication_date_wins(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready.write_config(FULL_SENDING, max_age=90)
    ready.sql("DELETE FROM evidence")
    ready.sql(
        "INSERT INTO evidence (lead_id, url, observed_at, published_at, kind) VALUES"
        " (1, 'https://firm.example.com/old', ?, ?, 'fact'),"
        " (1, 'https://firm.example.com/recent', ?, ?, 'fact')",
        (TODAY.isoformat(), _days_ago(200), TODAY.isoformat(), _days_ago(10)),
    )

    cells = _review_row(ready, capsys)
    assert "https://firm.example.com/recent" in cells
    assert "https://firm.example.com/old" not in cells
    assert cells[cells.index("https://firm.example.com/recent") + 1] == "10"
    assert _evidence_refusals(ready, capsys) == []
