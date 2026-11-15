"""Tests for research-record loading and validation (R-5, R-6, R-9, R-25)."""

from __future__ import annotations

import copy
import csv
import json
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from cottonwood import validate
from cottonwood.validate import FileError, ProspectRecord, RawRecord, Rejection

TODAY = date(2026, 11, 30)  # Denver today when utc_now is 2026-12-01T00:00:00Z


def _valid() -> dict[str, Any]:
    return {
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _check(data: object, number: int = 2) -> ProspectRecord | Rejection:
    return validate.validate_record(RawRecord(number, data), TODAY)


def _line(data: object) -> str:
    result = _check(data)
    assert isinstance(result, Rejection), result
    return result.line()


def _without(path: tuple[str | int, ...]) -> dict[str, Any]:
    data = _valid()
    target: Any = data
    for part in path[:-1]:
        target = target[part]
    del target[path[-1]]
    return data


def _with(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    data = _valid()
    target: Any = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return data


# --- Schema (AC 1) -----------------------------------------------------------------------


def test_schema_ships_in_the_package_and_is_valid() -> None:
    resource = resources.files("cottonwood").joinpath("schemas", "research-record.schema.json")
    loaded = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(loaded)
    assert loaded == validate.schema()


def test_valid_record_validates() -> None:
    result = _check(_valid())
    assert isinstance(result, ProspectRecord)
    assert result.type == "direct_candidate"
    assert result.organization_name_norm == "acme dental test"
    assert result.organization_domain_norm == "acme-dental.example.com"
    assert result.verified_facts == ("Signed a lease at 12 Main St",)
    assert result.evidence[0].kind == "fact"
    assert result.is_test is False


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("type",), "type"),
        (("organization", "name"), "organization.name"),
        (("verified_facts",), "verified_facts"),
        (("hypothesis",), "hypothesis"),
        (("evidence",), "evidence"),
        (("evidence", 0, "url"), "evidence[0].url"),
        (("evidence", 0, "observed_at"), "evidence[0].observed_at"),
    ],
)
def test_missing_required_field_is_named(path: tuple[str | int, ...], field: str) -> None:
    assert _line(_without(path)) == f"rejected record 2: {field}: required"


def test_evidence_needs_excerpt_or_observation() -> None:
    data = _without(("evidence", 0, "excerpt"))
    assert _line(data) == "rejected record 2: evidence[0]: anyOf"
    data["evidence"][0]["observation"] = "Sign in the window says opening soon"
    result = _check(data)
    assert isinstance(result, ProspectRecord)
    assert result.evidence[0].observation == "Sign in the window says opening soon"
    assert result.evidence[0].excerpt is None


def test_unknown_key_is_rejected_by_name() -> None:
    assert _line(_with(("organization", "nmae"), "x")) == (
        "rejected record 2: organization.nmae: additionalProperties"
    )


def test_non_object_record_is_rejected() -> None:
    assert _line(["not", "a", "record"]) == "rejected record 2: record: type"


# --- Field rules (AC 2) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("type",), "prospect", "type: enum"),
        (("evidence",), [], "evidence: minItems"),
        (("evidence", 0, "url"), "ftp://acme.com/x", "evidence[0].url: url"),
        (("evidence", 0, "url"), "https://", "evidence[0].url: url"),
        (("evidence", 0, "observed_at"), "2026-02-30", "evidence[0].observed_at: date"),
        (("evidence", 0, "observed_at"), "2026-11-3", "evidence[0].observed_at: date"),
        (("evidence", 0, "observed_at"), "2026-12-01", "evidence[0].observed_at: not-future"),
        (("evidence", 0, "published_at"), "2026-12-25", "evidence[0].published_at: not-future"),
        (("contact",), {"email": "not-an-email"}, "contact.email: email"),
        (("contact",), {"name": "Pat Lee", "phone": "call me"}, "contact.phone: phone"),
        (("contact",), {"role": "Office manager"}, "contact: anyOf"),
        (("organization", "domain"), "not a domain", "organization.domain: domain"),
        (("organization", "name"), "!!!", "organization.name: name"),
    ],
)
def test_field_rules(path: tuple[str | int, ...], value: object, expected: str) -> None:
    assert _line(_with(path, value)) == f"rejected record 2: {expected}"


def test_record_id_is_shown_in_the_prefix() -> None:
    data = _with(("type",), "prospect")
    data["record_id"] = "acme-1"
    assert _line(data) == "rejected record 2 (acme-1): type: enum"


def test_observed_today_is_accepted() -> None:
    assert isinstance(_check(_with(("evidence", 0, "observed_at"), "2026-11-30")), ProspectRecord)


def test_contact_values_are_normalized() -> None:
    contact = {"name": "Pat Lee", "email": " Pat@Acme.Example.com ", "phone": "(801) 555-0100"}
    result = _check(_with(("contact",), contact))
    assert isinstance(result, ProspectRecord)
    assert result.contact is not None
    assert result.contact.email_norm == "pat@acme.example.com"
    assert result.contact.phone_e164 == "+18015550100"


# --- Money (AC 3) ------------------------------------------------------------------------


def test_value_with_basis_keeps_the_amount_text() -> None:
    result = _check(_with(("value",), {"amount": "250000.00", "basis": "founder-estimated"}))
    assert isinstance(result, ProspectRecord)
    assert result.value_amount == "250000.00"
    assert result.value_basis == "founder-estimated"


def test_amount_without_basis_is_rejected() -> None:
    assert _line(_with(("value",), {"amount": "250000.00"})) == (
        "rejected record 2: value.basis: required"
    )


def test_unknown_basis_is_rejected() -> None:
    assert _line(_with(("value",), {"amount": "1", "basis": "guess"})) == (
        "rejected record 2: value.basis: enum"
    )


@pytest.mark.parametrize("amount", ["2.5e5", "-1", "abc", "1,000", "", " 5"])
def test_amount_must_be_a_plain_decimal(amount: str) -> None:
    assert _line(_with(("value",), {"amount": amount, "basis": "unverified"})) == (
        "rejected record 2: value.amount: decimal"
    )


# --- Loading (AC 4) ----------------------------------------------------------------------

CSV_HEADER = [
    "record_id",
    "type",
    "organization_name",
    "organization_domain",
    "contact_name",
    "contact_email",
    "property_location",
    "verified_facts",
    "hypothesis",
    "founder_time_h",
    "value_amount",
    "value_basis",
    "referred_by",
    "is_test",
    "evidence_url",
    "evidence_observed_at",
    "evidence_excerpt",
    "evidence_kind",
]


def _json_pair() -> list[dict[str, Any]]:
    first = _valid()
    first["record_id"] = "acme-1"
    first["contact"] = {"name": "Pat Lee", "email": "pat@acme-dental.example.com"}
    first["property_location"] = "12 Main St"
    first["verified_facts"] = ["Signed a lease", "Opening in March"]
    first["founder_time_h"] = 0.5
    first["value"] = {"amount": "250000.00", "basis": "founder-estimated"}
    first["is_test"] = True
    second = copy.deepcopy(_valid())
    second["type"] = "relationship_prospect"
    second["organization"] = {"name": "Wasatch Property Partners"}
    second["referred_by"] = 7
    second["evidence"][0]["kind"] = "hypothesis"
    return [first, second]


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def test_csv_rows_equal_the_json_records(tmp_path: Path) -> None:
    rows = [
        {
            "record_id": "acme-1",
            "type": "direct_candidate",
            "organization_name": "Acme Dental (TEST)",
            "organization_domain": "acme-dental.example.com",
            "contact_name": "Pat Lee",
            "contact_email": "pat@acme-dental.example.com",
            "property_location": "12 Main St",
            "verified_facts": "Signed a lease\n\nOpening in March",
            "hypothesis": "May need a tenant improvement",
            "founder_time_h": "0.5",
            "value_amount": "250000.00",
            "value_basis": "founder-estimated",
            "referred_by": "",
            "is_test": "true",
            "evidence_url": "https://news.example.com/acme",
            "evidence_observed_at": "2026-11-20",
            "evidence_excerpt": "Acme Dental will open a second office",
            "evidence_kind": "",
        },
        {
            "record_id": "",
            "type": "relationship_prospect",
            "organization_name": "Wasatch Property Partners",
            "organization_domain": "",
            "contact_name": "",
            "contact_email": "",
            "property_location": "",
            "verified_facts": "Signed a lease at 12 Main St",
            "hypothesis": "May need a tenant improvement",
            "founder_time_h": "",
            "value_amount": "",
            "value_basis": "",
            "referred_by": "7",
            "is_test": "",
            "evidence_url": "https://news.example.com/acme",
            "evidence_observed_at": "2026-11-20",
            "evidence_excerpt": "Acme Dental will open a second office",
            "evidence_kind": "hypothesis",
        },
    ]
    path = tmp_path / "research.csv"
    _write_csv(path, CSV_HEADER, rows)
    records = validate.load_records(path)
    assert [record.number for record in records] == [1, 2]
    assert [record.data for record in records] == _json_pair()


def test_json_array_loads_numbered_records(tmp_path: Path) -> None:
    path = tmp_path / "research.json"
    path.write_text(json.dumps(_json_pair()), encoding="utf-8")
    records = validate.load_records(path)
    assert [(record.number, record.data) for record in records] == list(
        enumerate(_json_pair(), start=1)
    )
    assert all(isinstance(validate.validate_record(r, TODAY), ProspectRecord) for r in records)


def test_csv_bad_number_is_left_for_the_schema(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    row = {name: "" for name in CSV_HEADER}
    row.update(
        type="direct_candidate",
        organization_name="Acme",
        verified_facts="A fact",
        hypothesis="A guess",
        founder_time_h="half an hour",
        evidence_url="https://acme.example.com",
        evidence_observed_at="2026-11-20",
        evidence_excerpt="Quoted text",
    )
    _write_csv(path, CSV_HEADER, [row])
    (record,) = validate.load_records(path)
    result = validate.validate_record(record, TODAY)
    assert isinstance(result, Rejection)
    assert result.line() == "rejected record 1: founder_time_h: type"


def _file_cases(tmp_path: Path) -> dict[str, Path]:
    text = tmp_path / "research.txt"
    text.write_text("[]", encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    obj = tmp_path / "object.json"
    obj.write_text('{"records": []}', encoding="utf-8")
    no_url = tmp_path / "no-url.csv"
    _write_csv(no_url, [name for name in CSV_HEADER if name != "evidence_url"], [])
    return {
        "txt": text,
        "missing": tmp_path / "missing.json",
        "invalid-json": broken,
        "object": obj,
        "csv-no-url": no_url,
    }


@pytest.mark.parametrize("case", ["txt", "missing", "invalid-json", "object", "csv-no-url"])
def test_file_errors_name_the_path(tmp_path: Path, case: str) -> None:
    path = _file_cases(tmp_path)[case]
    with pytest.raises(FileError) as excinfo:
        validate.load_records(path)
    assert str(path) in str(excinfo.value)


def test_csv_unknown_column_is_a_file_error(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [*CSV_HEADER, "favourite_colour"], [])
    with pytest.raises(FileError, match="favourite_colour"):
        validate.load_records(path)


def test_empty_json_array_has_no_records(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    assert validate.load_records(path) == []
