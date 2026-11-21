"""Tests for email, phone, domain and name normalization."""

from __future__ import annotations

import pytest

from cottonwood.normalize import (
    normalize_domain,
    normalize_email,
    normalize_name,
    normalize_phone,
)


def test_email_is_trimmed_and_lower_cased() -> None:
    assert normalize_email("  Jane.Doe@Example.COM ") == "jane.doe@example.com"


@pytest.mark.parametrize("bad", ["no-at-sign", "a@b@c.com", "a@localhost", "@example.com", ""])
def test_invalid_email_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="email"):
        normalize_email(bad)


def test_email_with_whitespace_inside_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_email("jane doe@example.com")


def test_domain_drops_userinfo_before_the_host() -> None:
    assert normalize_domain("https://user@Example.com/x") == "example.com"


@pytest.mark.parametrize(
    "raw",
    ["(801) 555-0134", "801.555.0134", "1-801-555-0134", "+1 801 555 0134", "8015550134"],
)
def test_us_phone_numbers_become_e164(raw: str) -> None:
    assert normalize_phone(raw) == "+18015550134"


def test_international_phone_keeps_country_code() -> None:
    assert normalize_phone("+44 20 7183 8750") == "+442071838750"


@pytest.mark.parametrize("bad", ["555-0134", "+12", "+1 801 555 013", "call me", "", "+44+20"])
def test_invalid_phone_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="phone|numbers"):
        normalize_phone(bad)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://WWW.Example.com:443/about", "example.com"),
        ("example.com.", "example.com"),
        ("http://sub.example.co.uk/path?q=1", "sub.example.co.uk"),
        ("Example.com", "example.com"),
    ],
)
def test_domain_is_bare_host(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("bad", ["localhost", "https://", ""])
def test_invalid_domain_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="domain"):
        normalize_domain(bad)


def test_name_drops_punctuation_and_collapses_whitespace() -> None:
    assert normalize_name("  Jane   O'Neil, Jr. ") == "jane oneil jr"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("+44 20", id="too-short-4-digits"),
        pytest.param("+4412345678901234", id="too-long-16-digits"),
    ],
)
def test_international_numbers_outside_8_to_15_digits_are_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="international numbers"):
        normalize_phone(bad)


def test_international_numbers_at_the_8_and_15_digit_bounds_are_kept() -> None:
    assert normalize_phone("+44 123 456") == "+44123456"
    assert normalize_phone("+441234567890123") == "+441234567890123"
