"""Structure redaction for logs/traces (PRD §14.7).

Sentinel structures must not leak into logs, the privacy endpoint, doctor, or
the privacy CLI. Chemistry endpoints may still return SMILES/SVG to the local
browser because that is the user's own requested result.
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from openmolclaw.__main__ import run_doctor, run_privacy
from openmolclaw.app import create_app
from openmolclaw.privacy import redact_structure_text

SECRET_SMILES = "C[C@H](N999SECRET)C(=O)O"  # distinctive, structure-like
SECRET_MOLBLOCK = "\n  fake\n\n  0  0\nM  END\nSECRET_MARKER"
SECRET_INCHI = "InChI=1S/SECRET-CANARY"


def test_redactor_collapses_structure_like_text():
    assert redact_structure_text(SECRET_MOLBLOCK) == "[STRUCTURE_REDACTED]"
    assert redact_structure_text(SECRET_INCHI) == "[STRUCTURE_REDACTED]"
    assert redact_structure_text(SECRET_SMILES) == "[POSSIBLE_STRUCTURE_REDACTED]"


def test_redactor_leaves_harmless_text_and_nonstrings():
    assert redact_structure_text("request completed in 12ms") == "request completed in 12ms"
    assert redact_structure_text("") == ""
    assert redact_structure_text(None) is None
    assert redact_structure_text(42) == 42


def test_log_filter_scrubs_structures(caplog):
    logger = logging.getLogger("openmolclaw.app")  # filter installed at import
    with caplog.at_level(logging.INFO, logger="openmolclaw.app"):
        logger.info(SECRET_SMILES)
        logger.warning(SECRET_MOLBLOCK)
    assert "N999SECRET" not in caplog.text
    assert "SECRET_MARKER" not in caplog.text


def test_privacy_endpoint_has_no_structure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(config={"model": {"provider": "local"}})
    app.testing = True
    client = app.test_client()
    # Even after rendering a sentinel structure, /api/privacy carries none of it.
    client.post("/api/render", json={"smiles": "CCO"})
    text = json.dumps(client.get("/api/privacy").get_json())
    for canary in ("N999SECRET", "SECRET_MARKER", "SECRET-CANARY"):
        assert canary not in text


def test_doctor_and_privacy_cli_have_no_structure(capsys):
    run_doctor()
    run_privacy(as_json=True)
    out = capsys.readouterr().out
    for canary in ("N999SECRET", "SECRET_MARKER", "SECRET-CANARY"):
        assert canary not in out
