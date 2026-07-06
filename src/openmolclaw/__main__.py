"""OpenMolClaw command-line entry point.

Subcommands:

* ``openmolclaw doctor`` — check the local install: RDKit, Flask, the model
  provider config, a sample render, a workspace round-trip, and the tool
  registry. Exits non-zero if any core check fails.
* ``openmolclaw serve`` — run the local Flask app.
* ``openmolclaw list-tools`` — print the built-in chemistry tools (``--json``
  for the full provider-facing schemas).
* ``openmolclaw run-contracts`` — run the in-package contract suite (no network,
  no secrets). Exits non-zero on any failure.
* ``openmolclaw version`` — print the package version.

Standard-library only at import time.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__


def _check(label: str, fn) -> Tuple[bool, str]:
    try:
        detail = fn()
        return True, f"ok   {label}: {detail}"
    except Exception as e:  # noqa: BLE001 - doctor reports, never raises
        return False, f"FAIL {label}: {e}"


def run_doctor(config_path: Optional[str] = None) -> int:
    checks = []

    def rdkit_check():
        from rdkit import Chem

        mol = Chem.MolFromSmiles("c1ccccc1")
        assert mol is not None
        return f"benzene -> {Chem.MolToSmiles(mol)}"

    def flask_check():
        import importlib.metadata

        import flask  # noqa: F401 - import is the check

        return f"flask {importlib.metadata.version('flask')}"

    def render_check():
        from .chemistry.render import molecule_svg_dimensions, render_molecule_svg

        svg = render_molecule_svg("CCO", width=200, height=150)
        dims = molecule_svg_dimensions(svg)
        assert svg.lstrip().startswith("<?xml") or "<svg" in svg
        return f"ethanol SVG {dims}"

    def workspace_check():
        from .workspace.serialization import dumps, loads
        from .workspace.state import WorkspaceState

        state = WorkspaceState.new("doctor")
        alias = state.add("molecule", {"smiles": "CCO"})
        restored = loads(dumps(state.workspace))
        assert alias in restored.objects
        return f"round-trip {alias}"

    def registry_check():
        from .builtin_tools import build_default_registry

        reg = build_default_registry()
        return f"{len(reg.names())} tools: {', '.join(reg.names())}"

    def chat_check():
        # Import-only check: confirm the conversational loop is wired to the
        # tool registry. Never constructs a provider or touches the network.
        from .builtin_tools import build_default_registry
        from .harness.chat import run_chat_turn  # noqa: F401 - import is the check

        reg = build_default_registry()
        return f"chat loop ready — POST /api/chat over {len(reg.names())} tools"

    def provider_check():
        # describe_provider never constructs/calls a model — safe for any config.
        from .config import describe_provider, load_config

        cfg = load_config(config_path)
        info = describe_provider(cfg)
        bundled = "bundled" if info["bundled"] else "not bundled"
        return f"{info['provider']} / {info['model']} ({bundled})"

    def privacy_check():
        # Report the resolved privacy posture; never touches network or secrets.
        from .config import describe_provider, load_config
        from .privacy import describe_privacy, resolve_workspace_save_mode

        cfg = load_config(config_path)
        save_mode = resolve_workspace_save_mode(
            (cfg.get("workspace") or {}) if isinstance(cfg, dict) else {}
        )
        posture = describe_privacy(describe_provider(cfg), save_mode=save_mode)
        zdr = "ON" if posture["openrouter_zdr"] else "OFF"
        psm = "ON" if posture["private_structure_mode"] else "OFF"
        return (
            f"OpenRouter ZDR (Zero Data Retention) {zdr}, "
            f"data collection {'DENY' if posture['deny_data_collection'] else 'ALLOW'}, "
            f"fallbacks {'DISABLED' if not posture['allow_fallbacks'] else 'ENABLED'}, "
            f"workspace {posture['workspace_save_mode']}, "
            f"Private Structure Mode {psm}"
        )

    def contracts_check():
        from .contracts import run_contracts

        report = run_contracts()
        if not report["ok"]:
            failed = [f"{c['area']}::{c['name']}" for c in report["cases"] if not c["ok"]]
            raise AssertionError(f"{report['failed']} failing: {', '.join(failed)}")
        return f"{report['passed']}/{report['total']} contract checks pass"

    checks.append(_check("rdkit", rdkit_check))
    checks.append(_check("flask", flask_check))
    checks.append(_check("render", render_check))
    checks.append(_check("workspace", workspace_check))
    checks.append(_check("tool registry", registry_check))
    checks.append(_check("chat", chat_check))
    checks.append(_check("model provider config", provider_check))
    checks.append(_check("privacy posture", privacy_check))
    checks.append(_check("contracts", contracts_check))

    print(f"OpenMolClaw doctor — v{__version__}")
    ok_all = True
    for ok, line in checks:
        ok_all = ok_all and ok
        print("  " + line)
    print("PASS" if ok_all else "FAILED — see lines marked FAIL above")
    return 0 if ok_all else 1


def run_list_tools(as_json: bool = False) -> int:
    from .builtin_tools import build_default_registry

    reg = build_default_registry()
    if as_json:
        print(json.dumps(reg.specs(), indent=2))
        return 0
    print(f"OpenMolClaw tools ({len(reg.names())}):")
    for spec in reg.specs():
        fn = spec["function"]
        print(f"  {fn['name']:<18} {fn.get('description', '')}")
    return 0


def run_privacy(config_path: Optional[str] = None, as_json: bool = False) -> int:
    """Print the resolved privacy posture for a config (no network, no secrets)."""
    from .config import describe_provider, load_config
    from .privacy import describe_privacy, resolve_workspace_save_mode

    cfg = load_config(config_path)
    info = describe_provider(cfg)
    save_mode = resolve_workspace_save_mode(
        (cfg.get("workspace") or {}) if isinstance(cfg, dict) else {}
    )
    posture = describe_privacy(info, save_mode=save_mode)
    if as_json:
        print(json.dumps(posture, indent=2, sort_keys=True))
        return 0

    def onoff(flag: bool, on: str = "ON", off: str = "OFF") -> str:
        return on if flag else off

    print(f"Provider: {posture['provider']}")
    print(f"Model: {info.get('model')}")
    print(f"OpenRouter ZDR (Zero Data Retention): {onoff(posture['openrouter_zdr'])}")
    print(f"Provider data collection: {onoff(posture['deny_data_collection'], 'DENY', 'ALLOW')}")
    print(f"Fallbacks: {onoff(posture['allow_fallbacks'], 'ENABLED', 'DISABLED')}")
    print(f"Require parameters: {onoff(posture['require_parameters'])}")
    print(f"Workspace save mode: {posture['workspace_save_mode']}")
    print(f"ChemIllusion server storage: {onoff(posture['chemillusion_server_storage'], 'YES', 'NO')}")
    print(f"Private Structure Mode: {onoff(posture['private_structure_mode'])}")
    print(f"  Blocks external molecule lookups: {onoff(posture['blocks_external_lookup'])}")
    if posture["private_structure_mode_claim"]:
        print(f"  Claim: {posture['private_structure_mode_claim']}")
    if posture["warnings"]:
        print("Notes:")
        for w in posture["warnings"]:
            print(f"  - {w}")
    return 0


def run_contracts_cli() -> int:
    from .contracts import format_report, run_contracts

    report = run_contracts()
    print(format_report(report))
    return 0 if report["ok"] else 1


def install_ketcher(archive: str, target: Optional[str] = None) -> int:
    from .app import WEB_DIR

    target_dir = Path(target) if target else WEB_DIR / "vendor" / "ketcher"

    # Current upstream Ketcher release zips (ketcher-standalone*.zip, 3.x) ship
    # only the npm library, not a demo index.html. Building the `example`
    # workspace from source instead produces a build *directory*, so accept
    # that directly alongside archives/URLs (see web/vendor/ketcher/README.md).
    local_path = Path(archive)
    if not archive.startswith(("http://", "https://")) and local_path.is_dir():
        index_files = list(local_path.rglob("index.html"))
        if not index_files:
            raise SystemExit(f"directory did not contain a Ketcher index.html: {archive}")
        source_root = index_files[0].parent
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root, target_dir, dirs_exist_ok=True)
        print(f"Installed Ketcher into {target_dir}")
        return 0

    with tempfile.TemporaryDirectory(prefix="openmolclaw-ketcher-") as td:
        tmp = Path(td)
        archive_path = tmp / "ketcher.archive"
        if archive.startswith(("http://", "https://")):
            urllib.request.urlretrieve(archive, archive_path)  # noqa: S310 - user-supplied CLI URL
        else:
            archive_path = local_path
        extract_dir = tmp / "extract"
        extract_dir.mkdir()
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(extract_dir)
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path) as tf:
                tf.extractall(extract_dir)
        else:
            raise SystemExit(f"unsupported Ketcher archive format: {archive}")

        index_files = list(extract_dir.rglob("index.html"))
        if not index_files:
            raise SystemExit("archive did not contain a Ketcher index.html")
        source_root = index_files[0].parent
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root, target_dir, dirs_exist_ok=True)
    print(f"Installed Ketcher into {target_dir}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="openmolclaw")
    sub = parser.add_subparsers(dest="command")

    p_doctor = sub.add_parser("doctor", help="check the local install")
    p_doctor.add_argument("--config", default=None, help="path to a model config YAML/JSON")

    p_serve = sub.add_parser("serve", help="run the local Flask app")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.add_argument("--config", default=None, help="path to a model config YAML/JSON")
    p_serve.add_argument("--workspace-id", default="local", help="workspace identifier")

    p_tools = sub.add_parser("list-tools", help="list built-in chemistry tools")
    p_tools.add_argument("--json", action="store_true", help="print full tool schemas as JSON")

    sub.add_parser("run-contracts", help="run the in-package contract suite")
    sub.add_parser("version", help="print the package version")

    p_privacy = sub.add_parser("privacy", help="print the resolved privacy posture")
    p_privacy.add_argument("--config", default=None, help="path to a model config YAML/JSON")
    p_privacy.add_argument("--json", action="store_true", help="print the posture as JSON")

    p_ketcher = sub.add_parser("install-ketcher", help="install a Ketcher standalone archive")
    p_ketcher.add_argument("--archive", required=True, help="local path or URL to a Ketcher archive")
    p_ketcher.add_argument("--target", default=None, help="target directory; defaults to package web/vendor/ketcher")

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return run_doctor(args.config)
    if args.command == "serve":
        from .app import create_app
        from .config import load_config

        cfg = load_config(args.config)
        create_app(config=cfg, workspace_id=args.workspace_id).run(
            host=args.host, port=args.port
        )
        return 0
    if args.command == "list-tools":
        return run_list_tools(as_json=args.json)
    if args.command == "run-contracts":
        return run_contracts_cli()
    if args.command == "privacy":
        return run_privacy(args.config, as_json=args.json)
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "install-ketcher":
        return install_ketcher(args.archive, args.target)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
