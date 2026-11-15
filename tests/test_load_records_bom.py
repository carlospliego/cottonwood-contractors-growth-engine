# sir-target: tests/test_load_records_bom.py
"""A UTF-8 BOM at the start of a research file must not break loading."""

from __future__ import annotations

from pathlib import Path

from cottonwood.validate import load_records

BOM = "﻿"


def test_json_with_bom_loads(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    path.write_text(BOM + '[{"record_id": "a-1"}]', encoding="utf-8")
    records = load_records(path)
    assert [(r.number, r.data) for r in records] == [(1, {"record_id": "a-1"})]


def test_csv_with_bom_loads_first_header(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    header = (
        "type,organization_name,verified_facts,hypothesis,"
        "evidence_url,evidence_observed_at,evidence_excerpt"
    )
    row = "direct_candidate,Acme,fact,guess,https://example.com/a,2026-11-20,quote"
    path.write_text(BOM + header + "\n" + row + "\n", encoding="utf-8")
    records = load_records(path)
    assert len(records) == 1
    assert isinstance(records[0].data, dict)
    assert records[0].data["type"] == "direct_candidate"
