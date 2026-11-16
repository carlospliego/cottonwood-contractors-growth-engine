"""R-27: no email-sending credential is committed anywhere in the repository."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CREDENTIAL_NAMES = (
    "SMTP_PASS",
    "SMTP_PASSWORD",
    "SENDGRID_API_KEY",
    "MAILGUN_API_KEY",
    "POSTMARK_SERVER_TOKEN",
    "SES_SECRET",
    "MAIL_PASSWORD",
)
# An assignment (NAME=value, NAME: value, "NAME": "value") to a name containing one of the
# credential names, with a non-empty value. Comment lines are skipped before matching.
_ASSIGNMENT = re.compile(
    r"""["']?[A-Za-z0-9_]*(?:"""
    + "|".join(CREDENTIAL_NAMES)
    + r""")[A-Za-z0-9_]*["']?\s*[:=]\s*["']?(?P<value>[^\s"'#,}]+)""",
    re.IGNORECASE,
)
# An SMTP URL with a user:password@ part.
_SMTP_URL = re.compile(r"smtps?://[^\s/:@]+:[^\s/@]+@", re.IGNORECASE)
_COMMENT = re.compile(r"^\s*(?:#|//|;|--)")


def find_credentials(lines: Iterable[str]) -> list[int]:
    """1-based numbers of the lines that look like a committed sending credential."""
    hits = []
    for number, line in enumerate(lines, start=1):
        if _COMMENT.match(line):
            continue
        if _ASSIGNMENT.search(line) or _SMTP_URL.search(line):
            hits.append(number)
    return hits


@pytest.mark.parametrize(
    "line",
    [
        "SMTP_PASSWORD=hunter2",
        "SENDGRID_API_KEY: SG.abc",
        "MAILGUN_API_KEY=key-1",
        "POSTMARK_SERVER_TOKEN=x",
        "SES_SECRET=y",
        "MAIL_PASSWORD=z",
        "SMTP_PASS=a",
        "smtp://user:secret@mail.example:587",
        'export APP_SMTP_PASSWORD="s3cret"',
        '{"sendgrid_api_key": "SG.xyz"}',
    ],
)
def test_credential_lines_are_flagged(line: str) -> None:
    assert find_credentials([line]) == [1]


@pytest.mark.parametrize(
    "line",
    [
        "# SMTP_PASSWORD=",
        "# SMTP_PASSWORD=hunter2",
        "SMTP_PASSWORD=",
        'SMTP_PASSWORD=""',
        "smtp://mail.example:587",
        "Email-sending credentials never belong here or anywhere in this repo (R-27):",
    ],
)
def test_harmless_lines_are_not_flagged(line: str) -> None:
    assert find_credentials([line]) == []


def test_env_template_is_not_flagged() -> None:
    template = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert find_credentials(template) == []


def _tracked_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [ROOT / name for name in listed.split("\0") if name]


def test_no_tracked_file_holds_a_sending_credential() -> None:
    hits = []
    this_file = Path(__file__).resolve()
    for path in _tracked_files():
        if path.resolve() == this_file or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += [f"{path.relative_to(ROOT)}:{n}" for n in find_credentials(text.splitlines())]
    assert hits == []
