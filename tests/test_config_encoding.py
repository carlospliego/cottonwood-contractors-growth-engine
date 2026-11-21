# sir-target: tests/test_config_encoding.py
"""A config file that is not valid UTF-8 raises ConfigError naming it (F-correctness-4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config


def test_non_utf8_config_raises_config_error_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(config.ConfigError) as raised:
        config.load_config(path)
    assert str(path) in str(raised.value)
    assert "UTF-8" in str(raised.value)
