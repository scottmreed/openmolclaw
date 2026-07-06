"""Remote runner template smoke tests."""

from __future__ import annotations

import subprocess
import sys

from openmolclaw.config import load_config


def test_remote_config_examples_load():
    openrouter = load_config("examples/config.remote.openrouter.zdr.yaml")
    assert openrouter["model"]["provider"] == "openrouter"
    assert openrouter["model"]["privacy"]["openrouter_zdr"] is True
    assert openrouter["workspace"]["save_mode"] == "memory_only"

    local = load_config("examples/config.remote.local.yaml")
    assert local["model"]["provider"] == "local"
    assert local["workspace"]["save_mode"] == "memory_only"


def test_slurm_tunnel_helper_prints_login_tunnel_command():
    result = subprocess.run(
        [
            "scripts/slurm/tunnel_from_job.sh",
            "--login",
            "user@login.cluster.edu",
            "--node",
            "compute-12.cluster.edu",
            "--port",
            "5050",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        result.stdout.strip()
        == "ssh -N -L 5050:compute-12.cluster.edu:5050 user@login.cluster.edu"
    )


def test_modal_template_compiles():
    subprocess.run(
        [sys.executable, "-m", "py_compile", "deploy/modal_app.py"],
        check=True,
    )
