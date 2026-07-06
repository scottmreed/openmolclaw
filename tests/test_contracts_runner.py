"""The in-package contract suite must pass with no network / no secrets."""

from __future__ import annotations

from openmolclaw.contracts import format_report, run_contracts


def test_all_contracts_pass():
    report = run_contracts()
    assert report["ok"], format_report(report)
    assert report["failed"] == 0
    assert report["passed"] == report["total"] >= 20


def test_report_covers_required_areas():
    areas = set(run_contracts()["areas"])
    required = {
        "name_resolution",
        "smiles",
        "tool_schemas",
        "error_envelopes",
        "provider_policy",
    }
    assert required.issubset(areas), areas
