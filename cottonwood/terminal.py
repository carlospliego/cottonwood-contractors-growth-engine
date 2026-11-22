"""Text that is safe to print to a terminal."""

from __future__ import annotations

import unicodedata


def printable(text: str) -> str:
    """``text`` without control or format characters (ESC, CR, bidi overrides and the like).

    Values read from research files are printed in import lines; a terminal escape or a
    carriage return in one could rewrite what the developer sees (F-security-basics-2).
    """
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))
