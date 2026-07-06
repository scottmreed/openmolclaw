"""CLI acceptance: every subcommand exits cleanly and prints something useful."""

from __future__ import annotations

from openmolclaw.__main__ import main


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() != ""


def test_list_tools(capsys):
    assert main(["list-tools"]) == 0
    out = capsys.readouterr().out
    for name in ("validate_smiles", "render_molecule", "convert_smiles", "lookup_compound"):
        assert name in out


def test_list_tools_json(capsys):
    import json

    assert main(["list-tools", "--json"]) == 0
    specs = json.loads(capsys.readouterr().out)
    assert isinstance(specs, list) and len(specs) == 14
    assert all(s["type"] == "function" for s in specs)


def test_run_contracts(capsys):
    assert main(["run-contracts"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_doctor(capsys):
    assert main(["doctor"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_serve_loads_config_and_workspace_id(tmp_path, monkeypatch):
    from openmolclaw import app as app_module

    cfg_path = tmp_path / "remote.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "model:",
                "  provider: local",
                "  model: remote-local",
                "  endpoint: http://127.0.0.1:11434/v1",
                "workspace:",
                "  save_mode: memory_only",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    class FakeApp:
        def run(self, *, host, port):
            captured["host"] = host
            captured["port"] = port

    def fake_create_app(*, config=None, workspace_id="local"):
        captured["config"] = config
        captured["workspace_id"] = workspace_id
        return FakeApp()

    monkeypatch.setattr(app_module, "create_app", fake_create_app)

    assert (
        main(
            [
                "serve",
                "--host",
                "0.0.0.0",
                "--port",
                "5050",
                "--config",
                str(cfg_path),
                "--workspace-id",
                "slurm-123",
            ]
        )
        == 0
    )

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 5050
    assert captured["workspace_id"] == "slurm-123"
    assert captured["config"]["model"]["model"] == "remote-local"
    assert captured["config"]["workspace"]["save_mode"] == "memory_only"


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_install_ketcher_from_local_archive(tmp_path, capsys):
    import zipfile

    archive = tmp_path / "ketcher.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ketcher-standalone/index.html", "<!doctype html><title>Ketcher</title>")
        zf.writestr("ketcher-standalone/static/app.js", "console.log('ketcher')")

    target = tmp_path / "vendor" / "ketcher"
    assert main(["install-ketcher", "--archive", str(archive), "--target", str(target)]) == 0
    assert (target / "index.html").exists()
    assert (target / "static" / "app.js").exists()
    assert "Installed Ketcher" in capsys.readouterr().out
