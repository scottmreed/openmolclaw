"""OpenMolClaw contract runner (in-package).

Runs the deterministic, no-network contract checks in :mod:`.checks` and returns
a structured report. Used by:

* the CLI: ``openmolclaw run-contracts``,
* the Flask app: ``GET /api/contracts``,
* pytest: ``tests/test_contracts_runner.py``.

The report shape is stable::

    {
      "ok": bool,
      "total": int, "passed": int, "failed": int,
      "areas": ["name_resolution", "smiles", ...],
      "cases": [
        {"area": str, "name": str, "ok": bool, "detail": str}, ...
      ],
    }

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .checks import CHECKS


def run_contracts() -> Dict[str, Any]:
    """Execute every contract check; return a structured pass/fail report."""
    cases: List[Dict[str, Any]] = []
    for area, name, fn in CHECKS:
        try:
            fn()
            cases.append({"area": area, "name": name, "ok": True, "detail": "ok"})
        except Exception as e:  # noqa: BLE001 - report, never raise
            cases.append(
                {
                    "area": area,
                    "name": name,
                    "ok": False,
                    "detail": f"{type(e).__name__}: {e}",
                }
            )
    passed = sum(1 for c in cases if c["ok"])
    areas: List[str] = []
    for c in cases:
        if c["area"] not in areas:
            areas.append(c["area"])
    return {
        "ok": passed == len(cases),
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "areas": areas,
        "cases": cases,
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render a human-readable summary of a contract report."""
    lines = [f"OpenMolClaw contracts — {report['passed']}/{report['total']} passed"]
    for c in report["cases"]:
        mark = "ok  " if c["ok"] else "FAIL"
        lines.append(f"  {mark} {c['area']}::{c['name']}" + ("" if c["ok"] else f" — {c['detail']}"))
    lines.append("PASS" if report["ok"] else "FAILED")
    return "\n".join(lines)


__all__ = ["run_contracts", "format_report"]
