"""Pilot configuration read from config/pilot.yaml (or $COTTONWOOD_CONFIG)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config") / "pilot.yaml"
CONFIG_ENV_VAR = "COTTONWOOD_CONFIG"
# Used when the file has no paths.backup_dir.
DEFAULT_BACKUP_DIR = Path("data") / "backups"


class ConfigError(Exception):
    """The configuration file is missing, unreadable or holds an invalid value."""


@dataclass(frozen=True)
class Config:
    """Typed pilot settings. Relative paths resolve against the current directory.

    model_cost_cap_usd is the monthly model-cost cap the report compares spend against (record
    only, never enforced); sending_blocked_by is the open question the report says blocks
    sending. Both are optional: None means no cap configured and nothing blocked.
    """

    backup_dir: Path
    model_cost_cap_usd: Decimal | None = None
    sending_blocked_by: str | None = None


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
        backup_dir=Path(backup_dir),
        model_cost_cap_usd=_cost_cap(report.get("model_cost_cap_usd"), config_path),
        sending_blocked_by=_blocked_by(report.get("sending_blocked_by"), config_path),
    )


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
