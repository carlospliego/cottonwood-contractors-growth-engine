"""Normalization of contact keys used for dedupe and suppression (R-2, R-24)."""

from __future__ import annotations

import re

_EMAIL_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
_PHONE_ALLOWED = re.compile(r"^\+?[0-9\s().-]+$")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")
_NAME_APOSTROPHES = re.compile(r"['\u2019]")
_NAME_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize_email(value: str) -> str:
    """Trim and lower-case an email address; reject one without a single @ and dotted domain."""
    email = value.strip().lower()
    if email.count("@") != 1:
        raise ValueError(f"email must contain exactly one @: {value!r}")
    local, domain = email.split("@")
    if any(ch.isspace() for ch in email):
        raise ValueError(f"email must not contain whitespace: {value!r}")
    if not local:
        raise ValueError(f"email has an empty local part: {value!r}")
    if not _EMAIL_DOMAIN.match(domain):
        raise ValueError(f"email domain must be a dotted name: {value!r}")
    return email


def normalize_phone(value: str) -> str:
    """Return a phone number in E.164 form, treating numbers without + as US (+1)."""
    text = value.strip()
    if not text or not _PHONE_ALLOWED.match(text) or text.count("+") > 1:
        raise ValueError(
            f"phone may only contain digits, spaces, ( ) . - and a leading +: {value!r}"
        )
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        if digits.startswith("1"):
            if len(digits) != 11:
                raise ValueError(
                    f"+1 numbers must have 10 digits after the country code: {value!r}"
                )
        elif not 8 <= len(digits) <= 15:
            raise ValueError(f"international numbers must have 8-15 digits: {value!r}")
        return f"+{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(f"US numbers must have 10 digits (or 11 with a leading 1): {value!r}")
    return f"+1{digits}"


def normalize_domain(value: str) -> str:
    """Return a bare lower-case host name: no scheme, www., port, path or trailing dot."""
    host = value.strip().lower()
    host = _SCHEME.sub("", host)
    host = re.split(r"[/?#]", host, maxsplit=1)[0]
    host = host.rsplit("@", 1)[-1]
    host = host.split(":", 1)[0].rstrip(".")
    # Strip www. only when a dotted host remains, so a host such as 'www.io' stays valid.
    if host.startswith("www.") and "." in host[4:]:
        host = host[4:]
    if not _EMAIL_DOMAIN.match(host):
        raise ValueError(f"domain must be a dotted host name: {value!r}")
    return host


def normalize_name(value: str) -> str:
    """Lower-case a name for matching only: apostrophes drop, other punctuation is a space.

    So 'Mary-Jane' and 'Mary Jane' match, and "O'Neil" stays one word ('oneil').
    """
    name = _NAME_APOSTROPHES.sub("", value.lower())
    name = _NAME_PUNCTUATION.sub(" ", name)
    return _WHITESPACE.sub(" ", name).strip()
