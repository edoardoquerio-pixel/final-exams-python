import json
import os
import subprocess
import sys

from fad_downloader.cli import main


def test_cli_demo_plan_and_download(tmp_path, capsys):
    workspace = str(tmp_path / "workspace")
    assert main(["plan", "--demo", "--workspace", workspace]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["tasks"]) == 3
    assert not (tmp_path / "workspace").exists()
    assert main(["download", "--demo", "--workspace", workspace]) == 0
    capsys.readouterr()
    assert main(["verify", "--workspace", workspace]) == 0
    assert json.loads(capsys.readouterr().out)["checked"] == 3


def test_cli_help_without_display_or_tk():
    env = dict(os.environ)
    env.pop("DISPLAY", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from fad_downloader.cli import parser; import sys; parser().print_help(); assert 'tkinter' not in sys.modules",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "download" in result.stdout


def test_cli_offline_catalog_backup_restore(tmp_path, capsys):
    workspace = str(tmp_path / "workspace")
    assert main(["scan", "--demo", "--workspace", workspace]) == 0
    capsys.readouterr()
    assert main(["catalog", "--workspace", workspace]) == 0
    assert len(json.loads(capsys.readouterr().out)["resources"]) == 3
    assert main(["backup", "--workspace", workspace]) == 0
    folder = json.loads(capsys.readouterr().out)["backup"]
    assert main(["restore", "--workspace", workspace, "--backup", folder]) == 0
    capsys.readouterr()
    assert main(["recovery", "--workspace", workspace]) == 0
    assert folder in json.loads(capsys.readouterr().out)["backups"]
