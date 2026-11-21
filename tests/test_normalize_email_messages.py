# sir-target: tests/test_normalize_email_messages.py
"""normalize_email names whitespace and an empty local part separately (F-maintainability-4)."""

from __future__ import annotations

import pytest

from cottonwood.normalize import normalize_email


def test_whitespace_in_the_domain_is_reported_as_whitespace() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        normalize_email("jane@exa mple.com")


def test_empty_local_part_is_reported_as_local_part() -> None:
    with pytest.raises(ValueError, match="local part") as caught:
        normalize_email("@example.com")
    assert "whitespace" not in str(caught.value)
