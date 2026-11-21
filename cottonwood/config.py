"""Pilot configuration read from config/pilot.yaml (or $COTTONWOOD_CONFIG)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config") / "pilot.yaml"
CONFIG_ENV_VAR = "COTTONWOOD_CONFIG"
# Used when the file has no paths.backup_dir.
DEFAULT_BACKUP_DIR = Path("data") / "backups"
# The candidate queues that have a checklist in review.checklists (R-13).
REVIEW_QUEUES = ("direct_candidate", "relationship_prospect")
CHECKLIST_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


class ConfigError(Exception):
    """The configuration file is missing, unreadable or holds an invalid value."""


@dataclass(frozen=True)
class ChecklistItem:
    """One yes/no/unknown checklist question of a candidate queue."""

    key: str
    label: str


def _empty_checklists() -> dict[str, tuple[ChecklistItem, ...]]:
    return {queue: () for queue in REVIEW_QUEUES}


@dataclass(frozen=True)
class ReviewConfig:
    """Checklist items per candidate queue and the optional maximum evidence age in days."""

    checklists: dict[str, tuple[ChecklistItem, ...]] = field(default_factory=_empty_checklists)
    max_evidence_age_days: int | None = None

    def keys(self) -> dict[str, frozenset[str]]:
        """The configured checklist keys per queue."""
        return {
            queue: frozenset(item.key for item in items) for queue, items in self.checklists.items()
        }


@dataclass(frozen=True)
class SendingConfig:
    """What every sendable draft must carry (R-21). Empty means not configured.

    prepare-send refuses while sender_identity or postal_address is empty, and checks that a
    draft contains each configured value verbatim; ad_identification is checked only when set.
    """

    sender_identity: str = ""
    postal_address: str = ""
    opt_out_line: str = ""
    ad_identification: str = ""


SENDING_KEYS = ("sender_identity", "postal_address", "opt_out_line", "ad_identification")


@dataclass(frozen=True)
class Config:
    """Typed pilot settings. Relative paths resolve against the current directory.

    model_cost_cap_usd is the monthly model-cost cap the report compares spend against (record
    only, never enforced); sending_blocked_by is the open question the report says blocks
    sending. Both are optional: None means no cap configured and nothing blocked. review holds
    the candidate-queue checklists and the maximum evidence age (none configured by default).
    """

    backup_dir: Path
    model_cost_cap_usd: Decimal | None = None
    sending_blocked_by: str | None = None
    review: ReviewConfig = field(default_factory=ReviewConfig)
    sending: SendingConfig = field(default_factory=SendingConfig)


def default_config_path() -> Path:
    """Return the config path: $COTTONWOOD_CONFIG when set, else config/pilot.yaml."""
    value = os.environ.get(CONFIG_ENV_VAR)
    return Path(value) if value else DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> Config:
    """Read the YAML mapping at ``path`` (default: default_config_path()).

    Unknown keys are ignored; a missing paths.backup_dir falls back to data/backups.
    """
    config_path = path if path is not None else default_config_path()
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"config file does not exist: {config_path}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"config file is not valid UTF-8: {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read config file {config_path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file is not valid YAML: {config_path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file must hold a mapping: {config_path}")
    paths = data.get("paths", {})
    if paths is None:
        paths = {}
    if not isinstance(paths, dict):
        raise ConfigError(f"paths must be a mapping in {config_path}")
    backup_dir = paths.get("backup_dir", str(DEFAULT_BACKUP_DIR))
    if not isinstance(backup_dir, str) or not backup_dir.strip():
        raise ConfigError(f"paths.backup_dir must be a non-empty string in {config_path}")
    report = data.get("report", {})
    if report is None:
        report = {}
    if not isinstance(report, dict):
        raise ConfigError(f"report must be a mapping in {config_path}")
    return Config(
        backup_dir=Path(backup_dir.strip()).expanduser(),
        model_cost_cap_usd=_cost_cap(report.get("model_cost_cap_usd"), config_path),
        sending_blocked_by=_blocked_by(report.get("sending_blocked_by"), config_path),
        review=_review(data.get("review"), config_path),
        sending=_sending(data.get("sending"), config_path),
    )


def _sending(value: object, config_path: Path) -> SendingConfig:
    """The sending block (R-21); a missing section or key is empty (not configured)."""
    if value is None:
        return SendingConfig()
    if not isinstance(value, dict):
        raise ConfigError(f"sending must be a mapping in {config_path}")
    values: dict[str, str] = {}
    for key in SENDING_KEYS:
        item = value.get(key)
        if item is None:
            values[key] = ""
        elif isinstance(item, str):
            values[key] = item.strip()
        else:
            raise ConfigError(f"sending.{key} must be a string in {config_path}")
    return SendingConfig(**values)


def _review(value: object, config_path: Path) -> ReviewConfig:
    """The review block: checklists per queue and max_evidence_age_days (R-10, R-13)."""
    if value is None:
        return ReviewConfig()
    if not isinstance(value, dict):
        raise ConfigError(f"review must be a mapping in {config_path}")
    checklists = value.get("checklists")
    if checklists is None:
        checklists = {}
    if not isinstance(checklists, dict):
        raise ConfigError(f"review.checklists must be a mapping in {config_path}")
    parsed = _empty_checklists()
    for queue, items in checklists.items():
        if queue not in REVIEW_QUEUES:
            raise ConfigError(
                f"review.checklists.{queue} is not a queue (expected one of"
                f" {', '.join(REVIEW_QUEUES)}) in {config_path}"
            )
        parsed[queue] = _checklist(f"review.checklists.{queue}", items, config_path)
    return ReviewConfig(
        checklists=parsed,
        max_evidence_age_days=_max_age(value.get("max_evidence_age_days"), config_path),
    )


def _checklist(path: str, items: object, config_path: Path) -> tuple[ChecklistItem, ...]:
    """One queue's checklist: a list of {key, label}, keys unique and lower_snake_case."""
    if items is None:
        return ()
    if not isinstance(items, list):
        raise ConfigError(f"{path} must be a list of {{key, label}} items in {config_path}")
    parsed: list[ChecklistItem] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{where} must be a mapping with key and label in {config_path}")
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ConfigError(f"{where}.key must be a non-empty string in {config_path}")
        key = key.strip()
        if CHECKLIST_KEY_PATTERN.fullmatch(key) is None:
            raise ConfigError(
                f"{where}.key must match ^[a-z][a-z0-9_]*$ in {config_path}, got {key!r}"
            )
        if key in seen:
            raise ConfigError(f"{where}.key {key!r} is a duplicate in {config_path}")
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ConfigError(f"{where}.label must be a non-empty string in {config_path}")
        seen.add(key)
        parsed.append(ChecklistItem(key, label.strip()))
    return tuple(parsed)


def _max_age(value: object, config_path: Path) -> int | None:
    """review.max_evidence_age_days as a positive whole number of days, or None when unset."""
    if value is None:
        return None
    # bool is an int subclass, so YAML's true/false must be refused explicitly.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(
            f"review.max_evidence_age_days must be a positive whole number of days in"
            f" {config_path}, got {value!r}"
        )
    return value


def _cost_cap(value: object, config_path: Path) -> Decimal | None:
    """report.model_cost_cap_usd as a finite, non-negative Decimal, or None when unset."""
    if value is None:
        return None
    message = (
        f"report.model_cost_cap_usd must be a non-negative number in {config_path}, got {value!r}"
    )
    # bool is an int subclass, so YAML's true/false must be refused explicitly.
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ConfigError(message)
    try:
        cap = Decimal(str(value).strip())
    except InvalidOperation:
        raise ConfigError(message) from None
    if not cap.is_finite() or cap < 0:
        raise ConfigError(message)
    return cap


def _blocked_by(value: object, config_path: Path) -> str | None:
    """report.sending_blocked_by stripped, or None when unset or blank."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"report.sending_blocked_by must be a string in {config_path}")
    return value.strip() or None
