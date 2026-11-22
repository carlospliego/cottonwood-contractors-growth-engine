"""R-27: no email-sending credential is committed anywhere in the repository.

The scan reads every file git lists (tracked, and untracked files not ignored), this one
included: its sample credential lines are joined from parts at run time.
"""

from __future__ import annotations

import re
import shutil
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


def _sample(*parts: str) -> str:
    """A sample line joined at run time, so this file's own source never holds one whole and
    the repository scan below can include this file with no exemption."""
    return "".join(parts)


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
        _sample("SMTP_", "PASSWORD=hunter2"),
        _sample("SENDGRID_", "API_KEY: SG.abc"),
        _sample("MAILGUN_", "API_KEY=key-1"),
        _sample("POSTMARK_", "SERVER_TOKEN=x"),
        _sample("SES_", "SECRET=y"),
        _sample("MAIL_", "PASSWORD=z"),
        _sample("SMTP_", "PASS=a"),
        _sample("smtp://user:", "secret@mail.example:587"),
        _sample("export APP_SMTP_", 'PASSWORD="s3cret"'),
        _sample('{"sendgrid_', 'api_key": "SG.xyz"}'),
    ],
)
def test_credential_lines_are_flagged(line: str) -> None:
    assert find_credentials([line]) == [1]


@pytest.mark.parametrize(
    "line",
    [
        "# SMTP_PASSWORD=",
        _sample("# SMTP_", "PASSWORD=hunter2"),
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


def _listed_files(root: Path) -> list[Path]:
    """Every file git knows of under ``root``: tracked, plus untracked files not ignored."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH; the R-27 credential scan lists files with git ls-files")
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        pytest.fail(f"git ls-files failed in {root}: {listed.stderr.decode(errors='replace')}")
    return [root / name for name in listed.stdout.decode("utf-8").split("\0") if name]


# sir's planning records (task contracts, specs, the todo index) quote the sample credential
# lines above as acceptance-criterion text; they are requirements, never configuration.
PLANNING_RECORDS = "work/"


def _is_exempt(relative: str) -> bool:
    """Whether a repo-relative path is a planning record the scan skips."""
    return relative.startswith(PLANNING_RECORDS)


@pytest.mark.parametrize(
    ("relative", "exempt"),
    [
        ("work/tasks/CCGE-113.md", True),
        ("work/specs/research-skill/tasks.json", True),
        ("config/pilot.yaml", False),
        ("cottonwood/cli.py", False),
        ("docs/runbook.md", False),
        (".env.example", False),
        ("tests/work/fixture.env", False),
    ],
)
def test_only_planning_records_are_exempt(relative: str, exempt: bool) -> None:
    assert _is_exempt(relative) is exempt


def _scanned_files(root: Path) -> list[tuple[str, Path]]:
    """(repo-relative path, path) of every file the scan reads under ``root``."""
    scanned = []
    for path in _listed_files(root):
        if not path.is_file():  # a tracked file deleted in the working tree
            continue
        relative = path.relative_to(root).as_posix()
        if not _is_exempt(relative):
            scanned.append((relative, path))
    return scanned


def scan(root: Path) -> list[str]:
    """PATH:LINE of every sending credential in a file git lists under ``root`` (R-27)."""
    hits = []
    for relative, path in _scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += [f"{relative}:{n}" for n in find_credentials(text.splitlines())]
    return hits


def test_no_listed_file_holds_a_sending_credential() -> None:
    assert scan(ROOT) == []


def test_the_scan_reads_this_file() -> None:
    this_file = Path(__file__).resolve()
    assert this_file in [path.resolve() for _relative, path in _scanned_files(ROOT)]


def _git_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH; the R-27 credential scan lists files with git ls-files")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_an_untracked_file_with_a_credential_is_reported(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "notes.txt").write_text("harmless\n" + _sample("SMTP_", "PASSWORD=hunter2\n"))
    assert scan(repo) == ["notes.txt:2"]


def test_an_ignored_file_is_not_scanned(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / ".gitignore").write_text("local-secrets.txt\n")
    (repo / "local-secrets.txt").write_text(_sample("SMTP_", "PASSWORD=hunter2\n"))
    assert scan(repo) == []


def test_the_scan_is_skipped_naming_git_when_git_is_not_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # an empty directory: no git
    with pytest.raises(pytest.skip.Exception, match="git is not on PATH"):
        scan(ROOT)
