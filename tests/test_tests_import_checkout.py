"""Tests import the checkout they run in, not the one the editable install points at (CCGE-063).

The uv editable install's ``.pth`` file names one checkout. A copy of the repository run
with that same interpreter (sir's mutant copies, a worktree without its own venv) used to
import the named checkout's ``cottonwood`` package, so a break in the copy went unnoticed.
``[tool.pytest.ini_options] pythonpath = ["."]`` puts the copy's own root first on
``sys.path``. These tests copy the repository, run one of its test files with this
interpreter, and check that the copy's code is the code under test.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = "tests/test_events_void_definition.py"
MARKER = "CCGE-063 deliberate break"


def _copy_repo(dest: Path) -> Path:
    copy = dest / "copy"
    copy.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", copy / "pyproject.toml")
    shutil.copytree(
        ROOT / "cottonwood", copy / "cottonwood", ignore=shutil.ignore_patterns("__pycache__")
    )
    (copy / "tests").mkdir()
    shutil.copy2(ROOT / TARGET, copy / TARGET)
    return copy


def _run(copy: Path) -> subprocess.CompletedProcess[str]:
    # The venv's pytest script, as `uv run pytest` starts it: unlike `python -m pytest`,
    # it does not put the working directory on sys.path.
    pytest_script = Path(sys.executable).parent / "pytest"
    return subprocess.run(
        [str(pytest_script), "-q", "-p", "no:cacheprovider", TARGET],
        cwd=copy,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_unbroken_copy_passes(tmp_path: Path) -> None:
    result = _run(_copy_repo(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_break_in_copy_events_fails_its_tests(tmp_path: Path) -> None:
    copy = _copy_repo(tmp_path)
    events = copy / "cottonwood" / "events.py"
    events.write_text(
        events.read_text(encoding="utf-8") + f"\nraise RuntimeError({MARKER!r})\n",
        encoding="utf-8",
    )
    result = _run(copy)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert MARKER in output
