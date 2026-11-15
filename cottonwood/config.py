"""Pilot configuration read from config/pilot.yaml (or $COTTONWOOD_CONFIG)."""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    """Typed pilot settings. Relative paths resolve against the current directory."""

    backup_dir: Path


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
    return Config(backup_dir=Path(backup_dir))
