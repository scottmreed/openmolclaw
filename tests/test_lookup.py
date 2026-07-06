"""Name/molecule resolution via an injected (offline) transport."""

from __future__ import annotations

from openmolclaw.chemistry import lookup


def _fetch_hit(url, timeout):  # noqa: ARG001
    payload = {"PropertyTable": {"Properties": [{"CID": 702, "IsomericSMILES": "CCO"}]}}
    return lookup.FetchResult(status_code=200, json=payload)


def _fetch_404(url, timeout):  # noqa: ARG001
    return lookup.FetchResult(status_code=404, json=None)


def test_name_to_smiles_hit():
    assert lookup.name_to_smiles("ethanol", fetch=_fetch_hit) == "CCO"


def test_name_to_smiles_or_none_miss():
    assert lookup.name_to_smiles_or_none("nope", fetch=_fetch_404) is None


def test_empty_name_raises():
    import pytest

    with pytest.raises(lookup.CompoundNotFound):
        lookup.name_to_smiles("   ", fetch=_fetch_hit)
