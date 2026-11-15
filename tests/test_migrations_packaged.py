# sir-target: tests/test_migrations_packaged.py
"""Regression for F-correctness-6: migrations must ship inside the cottonwood package."""

from __future__ import annotations

from pathlib import Path

import cottonwood
from cottonwood import db


def test_default_migrations_dir_is_inside_the_package() -> None:
    package_dir = Path(cottonwood.__file__).resolve().parent
    migrations_dir = db.MIGRATIONS_DIR.resolve()
    assert migrations_dir.is_relative_to(package_dir), (
        f"{migrations_dir} is outside {package_dir}; a wheel install would not ship it"
    )
    assert (migrations_dir / "001_baseline.sql").is_file()
