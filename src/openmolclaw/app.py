"""Local Flask app factory (OpenMolClaw).

A small local harness — *not* a re-creation of any hosted product's editor. It
serves the static Ketcher page bundled in the package's ``web/`` directory and
exposes the server-side surface a browser cannot do well, plus the harness's
tool/contract surface for programmatic callers.

Routes
------
Static / docs
    * ``GET  /``                     — the local Ketcher UI (or a JSON stub).
    * ``GET  /web/<path>``           — static assets for the UI.
    * ``GET  /docs``                 — minimal HTML API documentation.

Health + docs (machine-readable)
    * ``GET  /api/health``           — liveness + version + provider summary.
    * ``GET  /api/docs``             — JSON description of routes + tools.

Structure bridge
    * ``POST /api/smiles-to-molblock`` — SMILES → Molblock (PRD §13.2.5).
    * ``POST /api/molblock-to-smiles`` — read the current Ketcher structure back.
    * ``POST /api/validate``           — RDKit SMILES validation.
    * ``POST /api/render``             — render a validated molecule to SVG.

Tool / contract surface
    * ``GET  /api/tools``            — the stable tool contracts (schemas).
    * ``POST /api/tools/<name>``     — run one tool; returns the result envelope.
    * ``POST /api/execute``          — run a tool by ``{"tool": ..., "args": {}}``.
    * ``POST /api/chat``             — one chat turn: route → tools → reply.
    * ``GET  /api/contracts``        — run the in-package contract suite.

Workspace
    * ``GET/POST /api/workspace``    — inspect / append to the local workspace.

Standard-library + Flask + RDKit.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import hmac
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Flask, jsonify, request, send_from_directory
from rdkit import Chem

from . import __version__
from .builtin_tools import build_default_registry
from .chemistry import render, validate
from .config import (
    OPENROUTER_ZDR_MODEL_OPTIONS,
    UnknownProvider,
    build_provider,
    describe_provider,
    load_config,
    resolve_privacy_flags,
)
from .contracts import run_contracts
from .harness.chat import run_chat_turn
from .harness.defaults import (
    InMemoryWorkspaceStore,
    LocalJSONWorkspaceStore,
)
from .harness.executor import ToolExecutor
from .harness.interfaces import GateResult, ToolContext
from .privacy import (
    StructureRedactingLogFilter,
    coerce_bool,
    describe_privacy,
    resolve_workspace_save_mode,
)
from .workspace.state import WorkspaceState

logger = logging.getLogger("openmolclaw.app")
# Defense-in-depth: no OpenMolClaw log record may carry a raw structure, even by
# accident. The filter redacts structure-like text in messages/args.
if not any(isinstance(f, StructureRedactingLogFilter) for f in logger.filters):
    logger.addFilter(StructureRedactingLogFilter())

# The static web UI ships INSIDE the package (``openmolclaw/web``) so an
# installed wheel is self-contained.
WEB_DIR = Path(__file__).resolve().parent / "web"


class _PrivateStructureModeToolGate:
    """Host-level gate: blocks external structure lookups under Private
    Structure Mode.

    ``ToolGate`` is explicitly a host concern (see ``harness/interfaces.py`` —
    the generic harness has no opinion on this); this is the Flask app's
    policy. A name→SMILES lookup hits PubChem, so the query itself would leave
    the machine regardless of which model provider is configured — blocking it
    here is what lets ``describe_privacy`` honestly report
    ``blocks_external_lookup``.
    """

    _BLOCKED_TOOLS = frozenset({"lookup_compound"})

    def __init__(self, runtime: Dict[str, Any]) -> None:
        self._runtime = runtime

    def check(self, tool_name: str, context: ToolContext) -> GateResult:  # noqa: ARG002
        if tool_name in self._BLOCKED_TOOLS and self._runtime.get("private_structure_mode"):
            return GateResult.deny(
                "External structure lookup (PubChem) is disabled while Private "
                "Structure Mode is active — the lookup query would leave this "
                "machine. Turn off Private Structure Mode for this session to "
                "use lookup_compound, or work from a SMILES you already have."
            )
        return GateResult.allow()


def create_app(
    web_dir: Optional[Path] = None,
    workspace_id: str = "local",
    store: Optional[LocalJSONWorkspaceStore] = None,
    config: Optional[Dict[str, Any]] = None,
    provider_factory: Optional[Callable[[Optional[Dict[str, Any]]], Any]] = None,
) -> Flask:
    """Build the OpenMolClaw Flask app.

    ``config`` is an optional loaded model-provider config dict; when omitted the
    default local config is used. Nothing here requires network access or
    secrets — the provider summary is descriptive only and never calls a model.
    """
    web_root = Path(web_dir) if web_dir else WEB_DIR
    app = Flask(__name__, static_folder=None)
    cfg = config if config is not None else load_config()
    tools_cfg = (cfg.get("tools") or {}) if isinstance(cfg, dict) else {}
    include_deferred_rdkit_agent = coerce_bool(
        tools_cfg.get("rdkit_agent_deferred"),
        env="OPENMOLCLAW_TOOLS_RDKIT_AGENT_DEFERRED",
        default=True,
    )
    registry = build_default_registry(
        include_deferred_rdkit_agent=include_deferred_rdkit_agent
    )
    remote_token = os.environ.get("OPENMOLCLAW_REMOTE_TOKEN")

    # Workspace persistence: honor an explicitly supplied store; otherwise pick
    # a store from the resolved save mode. ``memory_only`` never writes to disk.
    # A mutable ``runtime`` holder lets the session-level privacy endpoint swap
    # the store (and thus the disk-persistence posture) without rebuilding app.
    workspace_cfg = (cfg.get("workspace") or {}) if isinstance(cfg, dict) else {}
    save_mode = resolve_workspace_save_mode(workspace_cfg)
    private_structure_mode = resolve_privacy_flags(
        (cfg.get("model") or {}) if isinstance(cfg, dict) else {}
    )["private_structure_mode"]
    # No silent weakening: Private Structure Mode always implies memory-only
    # workspace, even if ``workspace.save_mode`` was separately set to
    # ``local_json``.
    if private_structure_mode:
        save_mode = "memory_only"
    if store is None:
        store = (
            InMemoryWorkspaceStore()
            if save_mode == "memory_only"
            else LocalJSONWorkspaceStore()
        )
    runtime: Dict[str, Any] = {
        "store": store,
        "private_structure_mode": private_structure_mode,
    }

    def _sync_runtime_from_store() -> None:
        # Keep the reported save mode honest about the store actually in use.
        s = runtime["store"]
        if isinstance(s, InMemoryWorkspaceStore):
            runtime["save_mode"] = "memory_only"
            runtime["disk_path"] = None
        else:
            runtime["save_mode"] = "local_json"
            runtime["disk_path"] = str(getattr(s, "root", "")) or None

    _sync_runtime_from_store()

    def _privacy_payload() -> Dict[str, Any]:
        return describe_privacy(
            describe_provider(cfg),
            save_mode=runtime["save_mode"],
            local_workspace_disk_path=runtime["disk_path"],
        )

    def _executor() -> ToolExecutor:
        # A fresh executor per call keeps each request's trace isolated.
        return ToolExecutor(registry, tool_gate=_PrivateStructureModeToolGate(runtime))

    def _state() -> WorkspaceState:
        return WorkspaceState.load(runtime["store"], workspace_id)

    def _routes() -> list:
        return sorted(
            f"{sorted(r.methods - {'HEAD', 'OPTIONS'})} {r.rule}"
            for r in app.url_map.iter_rules()
            if r.endpoint != "static"
        )

    @app.before_request
    def require_remote_token():
        if not remote_token or not request.path.startswith("/api/"):
            return None
        auth = request.headers.get("Authorization", "")
        supplied = ""
        if auth.startswith("Bearer "):
            supplied = auth.removeprefix("Bearer ").strip()
        supplied = supplied or request.headers.get("X-OpenMolClaw-Token", "")
        if not hmac.compare_digest(supplied, remote_token):
            return jsonify({"ok": False, "error": "remote token required"}), 401
        return None

    # --- static UI --------------------------------------------------------
    @app.get("/")
    def index():
        if (web_root / "index.html").exists():
            return send_from_directory(web_root, "index.html")
        return jsonify(
            {
                "name": "OpenMolClaw",
                "version": __version__,
                "note": "web UI not found; API is available under /api/*, docs at /docs",
            }
        )

    @app.get("/web/<path:filename>")
    def web_assets(filename: str):
        return send_from_directory(web_root, filename)

    # --- health + docs ----------------------------------------------------
    @app.get("/api/health")
    def health():
        privacy = _privacy_payload()
        return jsonify(
            {
                "ok": True,
                "version": __version__,
                "provider": describe_provider(cfg),
                "tools": registry.names(),
                # A compact privacy summary; full detail at /api/privacy. Never
                # includes API keys or any structure content.
                "privacy": {
                    "provider": privacy["provider"],
                    "openrouter_zdr": privacy["openrouter_zdr"],
                    "workspace_save_mode": privacy["workspace_save_mode"],
                    "chemillusion_server_storage": privacy["chemillusion_server_storage"],
                },
            }
        )

    @app.get("/api/privacy")
    def privacy_route():
        # Full privacy posture: ZDR provider-routing controls + workspace save
        # mode + honest warnings. No secrets, no structure content.
        return jsonify(_privacy_payload())

    @app.post("/api/privacy/session")
    def privacy_session():
        # Session-level privacy overrides from the local UI. Updates the ZDR
        # provider-routing flags on the running config and can switch the
        # workspace store to memory-only (no disk) or back. Local app only.
        body: Dict[str, Any] = request.get_json(silent=True) or {}
        model_cfg = dict(cfg.get("model") or {})
        privacy = dict(model_cfg.get("privacy") or {})
        for key in (
            "openrouter_zdr",
            "deny_data_collection",
            "allow_fallbacks",
            "require_parameters",
            "private_structure_mode",
        ):
            if key in body:
                privacy[key] = bool(body[key])
        if privacy:
            model_cfg["privacy"] = privacy
            cfg["model"] = model_cfg
        runtime["private_structure_mode"] = bool(privacy.get("private_structure_mode", False))

        requested_mode = body.get("workspace_save_mode")
        # No silent weakening: Private Structure Mode always forces
        # memory-only, and a request to go back to local_json is ignored while
        # it is active — turn Private Structure Mode off first.
        if runtime["private_structure_mode"]:
            requested_mode = "memory_only"
        if requested_mode in ("memory_only", "local_json"):
            current = runtime["store"]
            if requested_mode == "memory_only" and not isinstance(
                current, InMemoryWorkspaceStore
            ):
                runtime["store"] = InMemoryWorkspaceStore()
            elif requested_mode == "local_json" and isinstance(
                current, InMemoryWorkspaceStore
            ):
                runtime["store"] = LocalJSONWorkspaceStore()
            _sync_runtime_from_store()

        return jsonify({"ok": True, **_privacy_payload()})

    @app.get("/docs")
    def docs_html():
        return _render_docs_html(registry, cfg, _routes())

    @app.get("/api/docs")
    def docs_json():
        return jsonify(
            {
                "name": "OpenMolClaw",
                "version": __version__,
                "attribution": "from the team behind ChemIllusion (https://chemillusion.com)",
                "provider": describe_provider(cfg),
                "privacy": _privacy_payload(),
                "routes": _routes(),
                "tools": registry.specs(),
            }
        )

    @app.get("/api/model-options")
    def model_options():
        return jsonify(
            {
                "recommended": "openrouter_zdr",
                "current": describe_provider(cfg),
                "privacy_note": (
                    "OpenRouter ZDR routes to endpoints marked zero-data-retention. "
                    "The endpoint still processes the request, but should not retain "
                    "or train on prompts according to OpenRouter's ZDR policy."
                ),
                "options": OPENROUTER_ZDR_MODEL_OPTIONS,
            }
        )

    @app.post("/api/model-options")
    def select_model_option():
        body: Dict[str, Any] = request.get_json(silent=True) or {}
        provider = str(body.get("provider") or "").strip()
        model = str(body.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"ok": False, "error": "provider and model are required"}), 400
        new_model: Dict[str, Any] = {
            "provider": provider,
            "model": model,
            "base_url": body.get("base_url") or "https://openrouter.ai/api/v1",
            "zdr": bool(body.get("zdr", False)),
            "require_tool_support": bool(body.get("require_tool_support", True)),
        }
        # Optional full privacy block from the caller (UI toggles / config).
        if isinstance(body.get("privacy"), dict):
            new_model["privacy"] = body["privacy"]
        cfg["model"] = new_model
        return jsonify(
            {"ok": True, "provider": describe_provider(cfg), "privacy": _privacy_payload()}
        )

    # --- structure bridge -------------------------------------------------
    @app.post("/api/smiles-to-molblock")
    def smiles_to_molblock():
        smiles = (request.get_json(silent=True) or {}).get("smiles", "")
        ok, detail = validate.validate_smiles_string(smiles)
        if not ok:
            return jsonify({"ok": False, "error": detail}), 400
        mol = Chem.MolFromSmiles(smiles)
        from rdkit.Chem import AllChem

        AllChem.Compute2DCoords(mol)
        return jsonify({"ok": True, "molblock": Chem.MolToMolBlock(mol)})

    @app.post("/api/molblock-to-smiles")
    def molblock_to_smiles():
        molblock = (request.get_json(silent=True) or {}).get("molblock", "")
        mol = Chem.MolFromMolBlock(molblock)
        if mol is None:
            return jsonify({"ok": False, "error": "could not parse Molblock"}), 400
        return jsonify({"ok": True, "smiles": Chem.MolToSmiles(mol)})

    @app.post("/api/validate")
    def validate_route():
        smiles = (request.get_json(silent=True) or {}).get("smiles", "")
        ok, detail = validate.validate_smiles_string(smiles)
        return jsonify({"ok": ok, "detail": detail})

    @app.post("/api/render")
    def render_route():
        body: Dict[str, Any] = request.get_json(silent=True) or {}
        smiles = body.get("smiles", "")
        try:
            svg = render.render_molecule_svg(
                smiles,
                width=int(body.get("width", 400)),
                height=int(body.get("height", 300)),
            )
        except render.RenderError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        # Persist into the local workspace so the object list can show it.
        state = _state()
        alias = state.add("molecule", {"smiles": smiles, "svg": svg})
        state.save(runtime["store"])
        return jsonify({"ok": True, "alias": alias, "svg": svg})

    # --- tool / contract surface -----------------------------------------
    @app.get("/api/tools")
    def list_tools():
        return jsonify({"tools": registry.specs()})

    @app.post("/api/tools/<name>")
    def run_named_tool(name: str):
        args = request.get_json(silent=True) or {}
        return _run_tool(_executor(), name, args)

    @app.post("/api/execute")
    def execute_tool():
        body = request.get_json(silent=True) or {}
        name = body.get("tool", "")
        args = body.get("args", {}) or {}
        return _run_tool(_executor(), name, args)

    # --- conversational chat (router → tools → responder) ----------------
    @app.post("/api/chat")
    def chat_route():
        """One conversational turn.

        Body: ``{"message": str, "history": [{"role","content"}, ...]}``. The
        client holds the history (privacy-friendly + stateless server), so a
        memory-only session keeps nothing on disk. Model/endpoint failures come
        back as a stable ``ok:false`` envelope with a user-facing ``reply`` —
        never a 500 — matching the tool surface's fail-closed style.
        """
        body: Dict[str, Any] = request.get_json(silent=True) or {}
        message = str(body.get("message", "")).strip()
        history = body.get("history") or []
        if not message:
            return (
                jsonify(
                    {"ok": False, "error": "message is required", "error_type": "bad_arguments"}
                ),
                400,
            )
        if not isinstance(history, list):
            return (
                jsonify(
                    {"ok": False, "error": "history must be a list", "error_type": "bad_arguments"}
                ),
                400,
            )

        try:
            provider = provider_factory(cfg) if provider_factory else build_provider(cfg)
        except UnknownProvider as e:
            return jsonify(
                {
                    "ok": False,
                    "error_type": "provider_not_configured",
                    "error": str(e),
                    "reply": (
                        "No model provider is configured. Point OpenMolClaw at a "
                        "local endpoint (no key needed) or an OpenRouter ZDR model "
                        "and try again — see /docs."
                    ),
                }
            )

        executor = ToolExecutor(registry, tool_gate=_PrivateStructureModeToolGate(runtime))
        try:
            turn = run_chat_turn(
                message,
                history,
                provider=provider,
                registry=registry,
                executor=executor,
            )
        except Exception as e:  # noqa: BLE001 - a model/endpoint failure must not 500 the app
            logger.warning("chat turn failed: %s", type(e).__name__)
            return jsonify(
                {
                    "ok": False,
                    "error_type": "provider_unavailable",
                    "error": str(e),
                    "reply": (
                        "I couldn't reach the configured model endpoint. If you're "
                        "running a local model, make sure it's up; if you're using a "
                        "hosted endpoint, check the model selection and API key. See /docs."
                    ),
                }
            )

        # Host concern (not the harness's): persist any structures the tools
        # produced into the local workspace so the UI can show them, and return
        # the deltas. Honors the active (possibly memory-only) store.
        deltas = []
        state = _state()
        changed = False
        structure_tools = {"render_molecule", "canonicalize_smiles", "lookup_compound"}
        for step in turn.steps:
            if not step.ok or not isinstance(step.result, dict):
                continue
            res = step.result
            smiles = (
                res.get("smiles")
                or res.get("canonical_smiles")
                or step.tool_args.get("smiles")
            )
            svg = res.get("svg")
            if svg or (smiles and step.tool_name in structure_tools):
                payload: Dict[str, Any] = {"smiles": smiles}
                if svg:
                    payload["svg"] = svg
                alias = state.add("molecule", payload)
                changed = True
                deltas.append({"alias": alias, "smiles": smiles, "svg": svg})
        if changed:
            state.save(runtime["store"])

        return jsonify(
            {
                "ok": True,
                "reply": turn.reply,
                "intent": turn.intent,
                "conversational": turn.conversational,
                "steps": [
                    {
                        "tool_name": s.tool_name,
                        "args": s.tool_args,
                        "ok": s.ok,
                        "result": s.result,
                        "error": s.error,
                        "error_type": s.error_type,
                    }
                    for s in turn.steps
                ],
                "trace": turn.trace,
                "workspace": deltas,
                "messages": turn.messages,
            }
        )

    @app.get("/api/contracts")
    def contracts_route():
        report = run_contracts()
        status = 200 if report["ok"] else 500
        return jsonify(report), status

    # --- workspace --------------------------------------------------------
    @app.get("/api/workspace")
    def get_workspace():
        state = _state()
        return jsonify(
            {"workspace_id": state.workspace.workspace_id, "objects": state.objects}
        )

    @app.post("/api/workspace")
    def add_workspace_object():
        body = request.get_json(silent=True) or {}
        object_type = body.get("type", "molecule")
        payload = {k: v for k, v in body.items() if k != "type"}
        state = _state()
        alias = state.add(object_type, payload)
        state.save(runtime["store"])
        return jsonify({"ok": True, "alias": alias})

    return app


def _run_tool(executor: ToolExecutor, name: str, args: Dict[str, Any]):
    """Run a tool and return its structured result envelope as JSON.

    Unknown tools / bad args / handler errors all come back as a stable envelope
    (never a 500 traceback): ``{"ok": false, "error": ..., "error_type": ...}``.
    """
    if not isinstance(args, dict):
        return (
            jsonify(
                {"ok": False, "error": "args must be an object", "error_type": "bad_arguments"}
            ),
            400,
        )
    result = executor.execute(name, args)
    payload = {
        "ok": result.ok,
        "tool_name": result.tool_name,
        "result": result.result,
        "error": result.error,
        "error_type": result.error_type,
        "duration_ms": round(result.duration_ms, 3),
    }
    status = 200 if result.ok else _status_for(result.error_type)
    return jsonify(payload), status


def _status_for(error_type: Optional[str]) -> int:
    return {
        "unknown_tool": 404,
        "gate_denied": 403,
        "bad_arguments": 400,
    }.get(error_type or "", 400 if error_type else 200)


def _render_docs_html(registry, cfg: Dict[str, Any], routes: list) -> str:
    """A single, dependency-free HTML page documenting the API surface."""
    tool_rows = "".join(
        f"<tr><td><code>{s['function']['name']}</code></td>"
        f"<td>{s['function'].get('description', '')}</td></tr>"
        for s in registry.specs()
    )
    route_items = "".join(f"<li><code>{r}</code></li>" for r in routes)
    provider = describe_provider(cfg)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clawd Science powered by OpenMolClaw — API v{__version__}</title>
<style>
  /* WCAG AA contrast in both light and dark; no purple (house rule). */
  :root {{
    color-scheme: light dark;
    --bg: #ffffff; --fg: #1a1d21; --muted: #4b5563; --link: #1d4ed8;
    --rule: rgba(0,0,0,0.18); --codebg: rgba(0,0,0,0.07);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0d1117; --fg: #e6edf3; --muted: #aeb6c2; --link: #7ca9ff;
      --rule: rgba(255,255,255,0.22); --codebg: rgba(255,255,255,0.10);
    }}
  }}
  body {{ background: var(--bg); color: var(--fg);
         font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 820px; margin: 2rem auto; padding: 0 1.25rem; line-height: 1.55; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .sub {{ color: var(--muted); margin-top: 0; }}
  code {{ background: var(--codebg); color: var(--fg); padding: 0.1rem 0.35rem; border-radius: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; }}
  td, th {{ border-bottom: 1px solid var(--rule); text-align: left;
           padding: 0.45rem 0.5rem; vertical-align: top; }}
  a {{ color: var(--link); }}
  ul {{ padding-left: 1.2rem; }}
</style></head>
<body>
  <h1>Clawd Science <small>powered by OpenMolClaw · v{__version__}</small></h1>
  <p class="sub">An open, local-first chemistry agent harness — from the team behind
     <a href="https://chemillusion.com">ChemIllusion</a>.</p>
  <p>Configured model provider: <code>{provider.get('provider')}</code> /
     <code>{provider.get('model')}</code>.
     Machine-readable docs at <a href="/api/docs"><code>/api/docs</code></a>;
     health at <a href="/api/health"><code>/api/health</code></a>.</p>
  <h2>Tools</h2>
  <table><thead><tr><th>name</th><th>description</th></tr></thead>
  <tbody>{tool_rows}</tbody></table>
  <h2>Routes</h2>
  <ul>{route_items}</ul>
</body></html>"""


def main(argv: Optional[list] = None) -> int:  # pragma: no cover - thin runner
    import argparse

    parser = argparse.ArgumentParser(prog="openmolclaw serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)
    create_app().run(host=args.host, port=args.port)
    return 0


__all__ = ["create_app", "main", "WEB_DIR"]
