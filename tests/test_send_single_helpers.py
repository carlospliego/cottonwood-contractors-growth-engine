# sir-target: tests/test_send_single_helpers.py
"""send.py writes activities through one helper and hashes through one helper.

F-maintainability-1 (review 20261115-191126): _insert_prepared duplicated _insert, and
prepare_send hashed the draft inline beside sha256_file, so a change to how activities are
written or digests computed had to be made in two places and could drift.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from cottonwood import send

SOURCE = Path(send.__file__).read_text(encoding="utf-8")


def _function_names() -> set[str]:
    tree = ast.parse(SOURCE)
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def test_there_is_no_separate_prepared_insert() -> None:
    assert "_insert_prepared" not in _function_names()
    assert SOURCE.count("INSERT INTO activities") == 1


def test_there_is_one_sha256_call() -> None:
    assert SOURCE.count("hashlib.sha256(") == 1


def test_the_file_digest_is_the_byte_digest(tmp_path: Path) -> None:
    data = b"Subject: hello\n\nBody \xe2\x80\x94 with a dash.\n"
    path = tmp_path / "draft.md"
    path.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert send.sha256_bytes(data) == expected
    assert send.sha256_file(path) == expected
