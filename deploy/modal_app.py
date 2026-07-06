"""Modal WSGI app template for OpenMolClaw.

Create the secret first:
    modal secret create openmolclaw-openrouter OPENROUTER_API_KEY="$OPENROUTER_API_KEY"

Then run:
    modal serve deploy/modal_app.py
    modal deploy deploy/modal_app.py
"""

from __future__ import annotations

import modal

app = modal.App("openmolclaw")

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "openmolclaw",
    "rdkit>=2023.9",
    "flask>=3.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "requests>=2.31",
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("openmolclaw-openrouter")],
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=20)
@modal.wsgi_app()
def flask_app():
    from openmolclaw.app import create_app

    cfg = {
        "model": {
            "provider": "openrouter",
            "model": "google/gemma-4-26b-a4b-it",
            "base_url": "https://openrouter.ai/api/v1",
            "require_tool_support": True,
            "preflight": False,
            "privacy": {
                "openrouter_zdr": True,
                "deny_data_collection": True,
                "allow_fallbacks": False,
                "require_parameters": True,
                "private_structure_mode": True,
            },
        },
        "workspace": {"save_mode": "memory_only"},
    }

    return create_app(config=cfg, workspace_id="modal")
