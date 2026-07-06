"""Compound lookup (OpenMolClaw chemistry).

Resolve a compound *name* to a SMILES string via the public PubChem PUG-REST
API. This is a clean extraction of the generic lookup path with all product
persistence and web-framework coupling removed: failures raise a plain
:class:`LookupError`, never a web exception.

The HTTP transport is injectable (``fetch=``). The default uses ``requests`` and
hits only PubChem's public endpoint; tests (and the contract suite) inject a
canned fetcher so name resolution is exercised deterministically with **no
network**.

Standard-library + ``requests`` (only when the default fetcher is used).

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Property names PubChem exposes, in preference order.
_PROPS = ("IsomericSMILES", "CanonicalSMILES")


class CompoundNotFound(LookupError):
    """Raised when a name cannot be resolved to a structure."""


@dataclass
class FetchResult:
    """Minimal HTTP result surface the lookup path needs from a transport."""

    status_code: int
    json: Optional[Dict[str, Any]] = None


#: A transport callable: ``fetch(url, timeout) -> FetchResult``.
Fetcher = Callable[[str, float], FetchResult]


def _requests_fetch(url: str, timeout: float) -> FetchResult:
    import requests

    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as e:  # pragma: no cover - network
        raise LookupError(f"PubChem request failed: {e}") from e
    payload: Optional[Dict[str, Any]]
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    return FetchResult(status_code=resp.status_code, json=payload)


def name_to_smiles(
    name: str,
    timeout: float = 20.0,
    fetch: Optional[Fetcher] = None,
) -> str:
    """Resolve a compound name to a SMILES via PubChem.

    Raises :class:`CompoundNotFound` if PubChem has no match, or
    :class:`LookupError` on transport / response failure. Pass ``fetch`` to
    supply a custom (e.g. offline canned) transport.
    """
    q = (name or "").strip()
    if not q:
        raise CompoundNotFound("empty compound name")

    do_fetch: Fetcher = fetch or _requests_fetch
    encoded = urllib.parse.quote(q, safe="")
    for prop in _PROPS:
        url = f"{PUBCHEM_BASE}/compound/name/{encoded}/property/{prop}/JSON"
        result = do_fetch(url, timeout)
        if result.status_code == 404:
            continue
        if result.status_code != 200:
            raise LookupError(f"PubChem returned HTTP {result.status_code} for {q!r}")
        try:
            props = result.json["PropertyTable"]["Properties"][0]  # type: ignore[index]
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise LookupError(f"unexpected PubChem response for {q!r}") from e
        smiles = props.get(prop) or props.get("CanonicalSMILES")
        if smiles:
            return smiles
    raise CompoundNotFound(f"no PubChem match for {q!r}")


def name_to_smiles_or_none(
    name: str,
    timeout: float = 20.0,
    fetch: Optional[Fetcher] = None,
) -> Optional[str]:
    """Non-raising variant: return the SMILES or ``None``."""
    try:
        return name_to_smiles(name, timeout=timeout, fetch=fetch)
    except LookupError:
        return None


__all__ = [
    "CompoundNotFound",
    "FetchResult",
    "Fetcher",
    "name_to_smiles",
    "name_to_smiles_or_none",
    "PUBCHEM_BASE",
]
