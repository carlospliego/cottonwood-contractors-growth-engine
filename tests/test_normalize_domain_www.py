# sir-target: tests/test_normalize_domain_www.py
"""normalize_domain strips www. only when a dotted host remains (F-correctness-7)."""

from __future__ import annotations

from cottonwood.normalize import normalize_domain


def test_www_io_stays_valid() -> None:
    assert normalize_domain("www.io") == "www.io"


def test_www_is_still_stripped_from_a_dotted_host() -> None:
    assert normalize_domain("https://www.example.com") == "example.com"
    assert normalize_domain("WWW.Example.co.uk/path") == "example.co.uk"
