"""The claims list that accompanies an outreach draft (R-20, R-21).

The drafting skill writes ``<draft stem>.claims.json`` next to each draft: a JSON array of
``{claim_id, status}`` validated against ``schemas/draft-claims.schema.json``. ``prepare-send``
reads only the claim ids from it; each claim's effective status is recomputed from the claims
library and the recorded claim approvals, never taken from this file.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_RESOURCE = ("schemas", "draft-claims.schema.json")


class DraftClaimsError(ValueError):
    """A claims list that cannot be used, naming the file."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


@cache
def schema() -> dict[str, Any]:
    """The draft-claims JSON Schema shipped inside the package."""
    resource = resources.files("cottonwood").joinpath(*SCHEMA_RESOURCE)
    loaded: dict[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    return loaded


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(schema())


def claims_list_path(draft: Path) -> Path:
    """The default claims list for a draft: the draft path with its suffix replaced."""
    return draft.with_suffix(".claims.json")


def load_draft_claims(path: Path) -> tuple[str, ...]:
    """The claim ids of a valid claims list, in file order, or raise DraftClaimsError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise DraftClaimsError(path, "claims list not found") from None
    except UnicodeDecodeError:
        raise DraftClaimsError(path, "claims list is not UTF-8 text") from None
    except OSError as exc:
        raise DraftClaimsError(
            path, f"cannot read the claims list: {exc.strerror or exc}"
        ) from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DraftClaimsError(path, f"claims list is not valid JSON: {exc.msg}") from None
    errors = sorted(_validator().iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.absolute_path) or "(top level)"
        raise DraftClaimsError(path, f"claims list is invalid at {where}: {first.message}")
    return tuple(str(item["claim_id"]) for item in data)
