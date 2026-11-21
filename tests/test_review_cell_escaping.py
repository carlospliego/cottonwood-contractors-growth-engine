"""Review table cells show inquirer-supplied Markdown and HTML as text (F-security-basics-1).

The founder reads the review as rendered Markdown, so a name, company or note that holds a
link, an image or raw HTML must reach it escaped, not as a clickable link or markup.
"""

from __future__ import annotations

import re

import pytest

from cottonwood import review

LINK = "[click here](https://evil.example/login)"
IMAGE = "![x](https://evil.example/pixel.png)"
HTML = '<a href="https://evil.example">Jane</a><script>alert(1)</script>'


def _unescaped(text: str, char: str) -> bool:
    """Whether char appears in text without a backslash in front of it."""
    return re.search(rf"(?<!\\){re.escape(char)}", text) is not None


@pytest.mark.parametrize("payload", [LINK, IMAGE, HTML, "`code` *bold* _em_"])
def test_metacharacters_are_escaped(payload: str) -> None:
    cell = review._cell(payload)
    for char in "[]()<>!`*_":
        assert not _unescaped(cell, char), (char, cell)


def test_link_payload_is_shown_literally() -> None:
    assert review._cell(LINK) == r"\[click here\]\(https://evil.example/login\)"


def test_html_payload_has_no_raw_tags() -> None:
    cell = review._cell(HTML)
    assert "<a" not in cell.replace("\\<", "")
    assert "<script>" not in cell
    assert cell.startswith(r"\<a href=")


def test_pipes_backslashes_and_lines_still_handled() -> None:
    assert review._cell("a|b\\c\nd") == r"a\|b\\c d"
    assert review._cell(None) == review.EMPTY
    assert review._cell("   ") == review.EMPTY


def test_plain_text_is_unchanged() -> None:
    assert review._cell("Jane Doe, Acme Roofing") == "Jane Doe, Acme Roofing"
