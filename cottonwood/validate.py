"""Research-record files: loading JSON or CSV and validating each record (R-5, R-6, R-9, R-25).

Validation never repairs input. A record either becomes a ProspectRecord with normalized
values or a Rejection naming the record, the field and the rule that failed.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, ValidationError

from cottonwood import events, normalize

SCHEMA_RESOURCE = ("schemas", "research-record.schema.json")
FILE_SUFFIXES = (".json", ".csv")
RELATIONSHIP = events.RELATIONSHIP_PROSPECT
DEFAULT_EVIDENCE_KIND = "fact"

# Rules Python checks after the schema passes (the schema keyword names the others).
RULE_URL = "url"
RULE_DATE = "date"
RULE_NOT_FUTURE = "not-future"
RULE_EMAIL = "email"
RULE_PHONE = "phone"
RULE_DOMAIN = "domain"
RULE_NAME = "name"
RULE_DECIMAL = "decimal"
# Python reads JSON Infinity/NaN and CSV "inf" as floats; the schema's minimum 0 passes them.
RULE_FINITE = "finite"
RULE_CHECKLIST_ITEM = "checklist-item"
# A CSV row with text in more cells than the header has columns: those cells would be lost.
FIELD_ROW = "row"
RULE_EXTRA_CELLS = "extra-cells"

CSV_COLUMNS = (
    "record_id",
    "type",
    "organization_name",
    "organization_domain",
    "organization_type",
    "organization_category",
    "contact_name",
    "contact_email",
    "contact_phone",
    "contact_address",
    "contact_role",
    "contact_source_url",
    "property_location",
    "verified_facts",
    "hypothesis",
    "next_action",
    "founder_time_h",
    "value_amount",
    "value_basis",
    "referred_by",
    "is_test",
    "evidence_url",
    "evidence_observed_at",
    "evidence_published_at",
    "evidence_excerpt",
    "evidence_observation",
    "evidence_kind",
)
# Required columns whose empty cell is a real empty value, as JSON allows ("hypothesis": "",
# "verified_facts": []), rather than an absent key that the schema rejects as required.
CSV_EMPTY_ALLOWED: dict[str, object] = {"hypothesis": "", "verified_facts": []}
CSV_REQUIRED = (
    "type",
    "organization_name",
    "verified_facts",
    "hypothesis",
    "evidence_url",
    "evidence_observed_at",
)
CSV_TEXT_EVIDENCE = ("evidence_excerpt", "evidence_observation")
# A column named checklist.KEY carries the answer to checklist item KEY (R-13).
CSV_CHECKLIST_PREFIX = "checklist."
# CSV column prefix → nested record key; the rest of the column name is the inner key.
_CSV_GROUPS = {"organization_": "organization", "contact_": "contact", "value_": "value"}

# [0-9] and \A...\Z, not \d and ^...$: \d also matches non-ASCII digits such as '١٠٠' and $ also
# matches before a trailing newline, so '100\n' would pass and be stored (F-correctness-2).
_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_PLAIN_DECIMAL = re.compile(r"\A[0-9]+(\.[0-9]+)?\Z")
_INTEGER = re.compile(r"\A[0-9]+\Z")
_BOOLEANS = {"true": True, "1": True, "false": False, "0": False}

FieldPath = tuple[str | int, ...]


class FileError(ValueError):
    """The file as a whole cannot be read as research records; nothing of it is imported."""


@dataclass(frozen=True)
class RawRecord:
    """One record as read from the file, before validation; ``number`` is 1-based.

    ``problem`` is a (field, rule) found while reading, such as a CSV row with extra cells; the
    record is rejected with it before any schema check.
    """

    number: int
    data: object
    problem: tuple[str, str] | None = None


@dataclass(frozen=True)
class Rejection:
    """Why one record was refused: the record, the field (a JSON path) and the rule."""

    number: int
    record_id: str | None
    field: str
    rule: str

    def label(self) -> str:
        """``record N`` with the record_id in parentheses when the record has one."""
        return record_label(self.number, self.record_id)

    def line(self) -> str:
        """The message the import prints for this rejection."""
        return f"rejected {self.label()}: {self.field}: {self.rule}"


@dataclass(frozen=True)
class ProspectContact:
    """A record's contact with its normalized keys."""

    name: str | None
    email: str | None
    email_norm: str | None
    phone: str | None
    phone_e164: str | None
    address: str | None
    role: str | None
    source_url: str | None


@dataclass(frozen=True)
class ProspectEvidence:
    """One evidence item; dates are YYYY-MM-DD strings."""

    url: str
    observed_at: str
    published_at: str | None
    excerpt: str | None
    observation: str | None
    kind: str


@dataclass(frozen=True)
class ProspectRecord:
    """A validated record, ready to import."""

    number: int
    record_id: str | None
    type: str
    organization_name: str
    organization_name_norm: str
    organization_domain: str | None
    organization_domain_norm: str | None
    organization_type: str | None
    organization_category: str | None
    contact: ProspectContact | None
    property_location: str | None
    verified_facts: tuple[str, ...]
    hypothesis: str
    next_action: str | None
    founder_time_h: float | None
    value_amount: str | None
    value_basis: str | None
    referred_by: int | None
    is_test: bool
    evidence: tuple[ProspectEvidence, ...]
    is_test_given: bool = False  # the record said is_test, so a stored value can differ
    # Checklist answers as (item key, yes/no/unknown) pairs sorted by key; () when absent.
    checklist: tuple[tuple[str, str], ...] = ()


def record_label(number: int, record_id: str | None) -> str:
    """How messages name a record."""
    return f"record {number}" if record_id is None else f"record {number} ({record_id})"


@cache
def schema() -> dict[str, Any]:
    """The research-record JSON Schema shipped inside the package."""
    resource = resources.files("cottonwood").joinpath(*SCHEMA_RESOURCE)
    loaded: dict[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    return loaded


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(schema())


# --- Loading -----------------------------------------------------------------------------


def load_records(path: Path) -> list[RawRecord]:
    """Read a .json (top-level array) or .csv research file into raw records.

    Raises FileError naming the path for a wrong extension, a missing or unreadable file,
    invalid JSON, a JSON top level that is not an array, or a CSV header that is incomplete
    or has unknown columns.
    """
    suffix = path.suffix.lower()
    if suffix not in FILE_SUFFIXES:
        raise FileError(f"{path}: research files must end in .json or .csv")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise FileError(f"file does not exist: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise FileError(f"cannot read {path}: {exc}") from None
    if suffix == ".json":
        return _json_records(path, text)
    return _csv_records(path, text)


def _json_records(path: Path, text: str) -> list[RawRecord]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileError(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(data, list):
        raise FileError(f"{path} must hold a JSON array of records")
    return [RawRecord(number, item) for number, item in enumerate(data, start=1)]


def _csv_records(path: Path, text: str) -> list[RawRecord]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    try:
        header = reader.fieldnames
    except csv.Error as exc:
        raise FileError(f"{path} is not valid CSV: {exc}") from None
    if header is None:
        raise FileError(f"{path} has no CSV header row")
    columns = [name.strip() for name in header]
    unknown = [
        name for name in columns if name not in CSV_COLUMNS and not _is_checklist_column(name)
    ]
    if unknown:
        raise FileError(f"{path}: unknown CSV column(s): {', '.join(unknown)}")
    missing = [name for name in CSV_REQUIRED if name not in columns]
    if not any(name in columns for name in CSV_TEXT_EVIDENCE):
        missing.append(" or ".join(CSV_TEXT_EVIDENCE))
    if missing:
        raise FileError(f"{path}: CSV header is missing column(s): {', '.join(missing)}")
    records = []
    try:
        for number, row in enumerate(reader, start=1):
            cells = {
                key.strip(): value
                for key, value in row.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            # DictReader puts cells past the last header column in a list under the key None;
            # dropping them would import a truncated row, so a row with text there is rejected.
            extra = row.get(None) or []
            problem = (
                (FIELD_ROW, RULE_EXTRA_CELLS)
                if any(isinstance(cell, str) and cell.strip() for cell in extra)
                else None
            )
            records.append(RawRecord(number, _csv_record(cells), problem))
    except csv.Error as exc:
        raise FileError(f"{path} is not valid CSV: {exc}") from None
    return records


def _csv_record(cells: Mapping[str, str]) -> dict[str, object]:
    """One CSV row in the JSON record shape: empty cells are absent; one evidence item.

    An empty hypothesis or verified_facts cell is the empty value (CSV_EMPTY_ALLOWED), so a CSV
    row can say "no hypothesis" or "no facts yet" just as a JSON record can.
    """
    record: dict[str, object] = {}
    evidence: dict[str, object] = {}
    groups: dict[str, dict[str, object]] = {}
    for column in CSV_COLUMNS:
        value = cells.get(column, "")
        if not value.strip():
            if column in CSV_EMPTY_ALLOWED and column in cells:
                empty = CSV_EMPTY_ALLOWED[column]
                record[column] = list(empty) if isinstance(empty, list) else empty
            continue
        if column.startswith("evidence_"):
            evidence[column.removeprefix("evidence_")] = value
            continue
        group = next((g for prefix, g in _CSV_GROUPS.items() if column.startswith(prefix)), None)
        if group is not None:
            inner = column.split("_", 1)[1]
            groups.setdefault(group, {})[inner] = value
            continue
        record[column] = _csv_scalar(column, value)
    for group, values in groups.items():
        record[group] = values
    if evidence:
        record["evidence"] = [evidence]
    checklist = {
        column.removeprefix(CSV_CHECKLIST_PREFIX): value
        for column, value in cells.items()
        if _is_checklist_column(column) and value.strip()
    }
    if checklist:
        record["checklist"] = checklist
    return record


def _is_checklist_column(name: str) -> bool:
    """True for a CSV column named checklist.KEY with a non-empty KEY."""
    return name.startswith(CSV_CHECKLIST_PREFIX) and bool(name.removeprefix(CSV_CHECKLIST_PREFIX))


def _csv_scalar(column: str, value: str) -> object:
    """Coerce typed CSV cells; text that does not parse is kept for the schema to reject."""
    if column == "verified_facts":
        return [line.strip() for line in value.splitlines() if line.strip()]
    if column == "founder_time_h":
        try:
            number = float(value)
        except ValueError:
            return value
        return number if number == number else value  # NaN stays text
    if column == "referred_by":
        stripped = value.strip()
        return int(stripped) if _INTEGER.match(stripped) else value
    if column == "is_test":
        return _BOOLEANS.get(value.strip().lower(), value)
    return value


# --- Validation --------------------------------------------------------------------------


def validate_record(
    raw: RawRecord,
    today: date,
    checklist_keys: Mapping[str, AbstractSet[str]] | None = None,
) -> ProspectRecord | Rejection:
    """Validate one raw record against the schema, then the rules the schema cannot express.

    ``today`` is the current date in America/Denver; observed and published dates may not be
    later. ``checklist_keys`` maps a record type to its configured checklist item keys; a
    checklist answer for any other key is rejected (none are allowed when it is omitted).
    Only the first failure, in field-path order, is reported, so output is stable.
    """
    record_id = _record_id(raw.data)
    if raw.problem is not None:
        return Rejection(raw.number, record_id, *raw.problem)
    errors = [_schema_failure(error) for error in _validator().iter_errors(raw.data)]
    if errors:
        field, rule = min(errors, key=_failure_order)
        return Rejection(raw.number, record_id, _render(field), rule)
    if not isinstance(raw.data, dict):  # the schema requires an object; this narrows the type
        return Rejection(raw.number, record_id, "record", "type")
    data: dict[str, Any] = raw.data
    allowed = (checklist_keys or {}).get(data["type"], frozenset())
    failures = list(_python_failures(data, today, allowed))
    if failures:
        field, rule = min(failures, key=_failure_order)
        return Rejection(raw.number, record_id, _render(field), rule)
    return _record(raw.number, record_id, data)


def _record_id(data: object) -> str | None:
    if isinstance(data, dict):
        value = data.get("record_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _schema_failure(error: ValidationError) -> tuple[FieldPath, str]:
    """The field path and rule of one schema error; a missing or extra key names itself."""
    path: FieldPath = tuple(error.absolute_path)
    rule = str(error.validator)
    instance = error.instance
    required = error.validator_value
    if rule == "required" and isinstance(instance, dict) and isinstance(required, list):
        missing = [key for key in required if key not in instance]
        if missing:
            path = (*path, str(missing[0]))
    elif rule == "additionalProperties" and isinstance(instance, dict):
        allowed = error.schema.get("properties", {}) if isinstance(error.schema, dict) else {}
        extra = sorted(str(key) for key in instance if key not in allowed)
        if extra:
            path = (*path, extra[0])
    return path, rule


def _failure_order(failure: tuple[FieldPath, str]) -> tuple[tuple[tuple[int, int, str], ...], str]:
    """Sort failures by path (indices numerically, keys alphabetically), then rule."""
    path, rule = failure
    key = tuple((1, part, "") if isinstance(part, int) else (0, 0, part) for part in path)
    return key, rule


def _render(path: FieldPath) -> str:
    """A JSON path like evidence[0].url; the record itself is 'record'."""
    text = ""
    for part in path:
        text += f"[{part}]" if isinstance(part, int) else (f".{part}" if text else part)
    return text or "record"


def _python_failures(
    data: Mapping[str, Any], today: date, checklist_keys: AbstractSet[str]
) -> Iterable[tuple[FieldPath, str]]:
    """Failures of the rules the schema leaves to Python, for a schema-valid record."""
    founder_time = data.get("founder_time_h")
    if founder_time is not None and not math.isfinite(founder_time):
        yield ("founder_time_h",), RULE_FINITE
    for key in data.get("checklist", {}):
        if key not in checklist_keys:
            yield ("checklist", key), RULE_CHECKLIST_ITEM
    organization = data["organization"]
    if not normalize.normalize_name(organization["name"]):
        yield ("organization", "name"), RULE_NAME
    if "domain" in organization and not _normalizes(
        normalize.normalize_domain, organization["domain"]
    ):
        yield ("organization", "domain"), RULE_DOMAIN
    contact = data.get("contact")
    if contact is not None:
        if "email" in contact and not _normalizes(normalize.normalize_email, contact["email"]):
            yield ("contact", "email"), RULE_EMAIL
        if "phone" in contact and not _normalizes(normalize.normalize_phone, contact["phone"]):
            yield ("contact", "phone"), RULE_PHONE
        if "source_url" in contact and not is_http_url(contact["source_url"]):
            yield ("contact", "source_url"), RULE_URL
    value = data.get("value")
    if value is not None and not _PLAIN_DECIMAL.match(value["amount"]):
        yield ("value", "amount"), RULE_DECIMAL
    for index, item in enumerate(data["evidence"]):
        if not is_http_url(item["url"]):
            yield ("evidence", index, "url"), RULE_URL
        for key in ("observed_at", "published_at"):
            if key in item:
                rule = _date_rule(item[key], today)
                if rule is not None:
                    yield ("evidence", index, key), rule


def _normalizes(normalizer: Callable[[str], str], value: str) -> bool:
    try:
        normalizer(value)
    except ValueError:
        return False
    return True


def is_http_url(value: str) -> bool:
    """True for an http(s) URL with a host and no whitespace."""
    if not value or any(ch.isspace() for ch in value):
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(host)


def _date_rule(value: str, today: date) -> str | None:
    """None for a real YYYY-MM-DD date not after today, else the failed rule."""
    if not _DATE.match(value):
        return RULE_DATE
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return RULE_DATE
    return RULE_NOT_FUTURE if day > today else None


def _text(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _record(number: int, record_id: str | None, data: Mapping[str, Any]) -> ProspectRecord:
    """Build the ProspectRecord of a record that passed every check."""
    organization = data["organization"]
    domain = _text(organization, "domain")
    contact = data.get("contact")
    value = data.get("value")
    founder_time = data.get("founder_time_h")
    return ProspectRecord(
        number=number,
        record_id=record_id,
        type=data["type"],
        organization_name=organization["name"].strip(),
        organization_name_norm=normalize.normalize_name(organization["name"]),
        organization_domain=domain,
        organization_domain_norm=None if domain is None else normalize.normalize_domain(domain),
        organization_type=_text(organization, "type"),
        organization_category=_text(organization, "category"),
        contact=None if contact is None else _contact(contact),
        property_location=_text(data, "property_location"),
        verified_facts=tuple(fact.strip() for fact in data["verified_facts"]),
        hypothesis=data["hypothesis"].strip(),
        next_action=_text(data, "next_action"),
        founder_time_h=None if founder_time is None else float(founder_time),
        value_amount=None if value is None else value["amount"],
        value_basis=None if value is None else value["basis"],
        referred_by=data.get("referred_by"),
        is_test=bool(data.get("is_test", False)),
        is_test_given="is_test" in data,
        evidence=tuple(_evidence(item) for item in data["evidence"]),
        checklist=tuple(sorted(data.get("checklist", {}).items())),
    )


def _contact(contact: Mapping[str, Any]) -> ProspectContact:
    email = _text(contact, "email")
    phone = _text(contact, "phone")
    return ProspectContact(
        name=_text(contact, "name"),
        email=email,
        email_norm=None if email is None else normalize.normalize_email(email),
        phone=phone,
        phone_e164=None if phone is None else normalize.normalize_phone(phone),
        address=_text(contact, "address"),
        role=_text(contact, "role"),
        source_url=_text(contact, "source_url"),
    )


def _evidence(item: Mapping[str, Any]) -> ProspectEvidence:
    return ProspectEvidence(
        url=item["url"],
        observed_at=item["observed_at"],
        published_at=item.get("published_at"),
        excerpt=_text(item, "excerpt"),
        observation=_text(item, "observation"),
        kind=item.get("kind", DEFAULT_EVIDENCE_KIND),
    )
