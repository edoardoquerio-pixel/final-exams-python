import json
import os
import subprocess
import sys

from fad_downloader.cli import main


def test_cli_selects_individual_objects(tmp_path, capsys):
    workspace = str(tmp_path / "workspace")
    options = ["--no-log"]
    assert main(options + ["plan", "--demo", "--workspace", workspace]) == 0
    tasks = json.loads(capsys.readouterr().out)["tasks"]
    chosen = next(t for t in tasks if t["type"] == "quiz_review")
    selection = ["--course-id", "1", "--resource-id", chosen["id"]]
    assert main(options + ["plan", "--demo", "--workspace", workspace] + selection) == 0
    assert json.loads(capsys.readouterr().out)["tasks"] == [chosen]
    assert not (tmp_path / "workspace").exists()
    assert main(options + ["download", "--demo", "--workspace", workspace] + selection) == 0
    assert len(json.loads(capsys.readouterr().out)["results"]) == 1
    assert main(options + ["plan", "--demo", "--resource-id", "missing"]) == 2
    capsys.readouterr()
    assert main(options + ["plan", "--demo", "--type", "materials"] + selection) == 2
    capsys.readouterr()
    assert main(options + ["download", "--demo", "--dry-run", "--resume"] + selection) == 2
    capsys.readouterr()
    assert main(options + ["download", "--demo", "--dry-run", "--copy-conflicts"] + selection) == 2
    capsys.readouterr()
    assert main(options + ["plan", "--demo", "--course-id", "999", "--resource-id", chosen["id"]]) == 2
    capsys.readouterr()
    multiple = ["--resource-id", tasks[0]["id"], "--resource-id", chosen["id"]]
    assert main(options + ["plan", "--demo", "--workspace", workspace] + multiple) == 0
    assert {t["id"] for t in json.loads(capsys.readouterr().out)["tasks"]} == {
        tasks[0]["id"], chosen["id"]
    }


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


def test_cli_two_database_users_and_pdf(tmp_path, capsys):
    database = str(tmp_path / "demo.sqlite3")
    for user in ("studente1", "studente2"):
        prefix = ["--database", database, "--db-user", user]
        assert main(prefix + ["download", "--demo", "--workspace", str(tmp_path / user)]) == 0
        capsys.readouterr()
        assert main(prefix + ["db-history", "--demo"]) == 0
        assert len(json.loads(capsys.readouterr().out)) == 3
        assert (
            main(prefix + ["report-pdf", "--demo", "--output", str(tmp_path / (user + ".pdf"))])
            == 0
        )
        assert (tmp_path / (user + ".pdf")).read_bytes().startswith(b"%PDF")
        capsys.readouterr()
