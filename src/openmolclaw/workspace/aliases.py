"""Semantic aliases (OpenMolClaw workspace).

Objects in the workspace are addressed by short, human-readable, type-prefixed
aliases: molecules are ``[m1] [m2] ...``, reactions ``[r1] ...``, and labels
``[label1] ...``. The model refers to objects by these aliases instead of
opaque ids, which keeps tool-call arguments legible in the execution trace.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable

# Object type -> alias prefix.
TYPE_PREFIX: Dict[str, str] = {
    "molecule": "m",
    "reaction": "r",
    "label": "label",
}

_ALIAS_RE = re.compile(r"^\[(?P<prefix>[a-zA-Z]+)(?P<num>\d+)\]$")


def prefix_for_type(object_type: str) -> str:
    try:
        return TYPE_PREFIX[object_type]
    except KeyError:
        raise ValueError(f"unknown object type: {object_type!r}")


def format_alias(object_type: str, number: int) -> str:
    return f"[{prefix_for_type(object_type)}{number}]"


def parse_alias(alias: str) -> tuple:
    """Return ``(prefix, number)`` for a well-formed alias like ``[m3]``."""
    m = _ALIAS_RE.match((alias or "").strip())
    if not m:
        raise ValueError(f"malformed alias: {alias!r}")
    return m.group("prefix"), int(m.group("num"))


def next_alias(object_type: str, existing: Iterable[str]) -> str:
    """Allocate the next free alias of ``object_type`` given existing aliases.

    Numbers are 1-based and monotonically increasing per prefix, so aliases are
    stable and never reused within a session even after deletions.
    """
    prefix = prefix_for_type(object_type)
    highest = 0
    for alias in existing:
        m = _ALIAS_RE.match(alias.strip())
        if m and m.group("prefix") == prefix:
            highest = max(highest, int(m.group("num")))
    return f"[{prefix}{highest + 1}]"


__all__ = [
    "TYPE_PREFIX",
    "prefix_for_type",
    "format_alias",
    "parse_alias",
    "next_alias",
]
