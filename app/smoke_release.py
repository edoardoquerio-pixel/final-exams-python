"""Prova offline del pacchetto installato, con dati soltanto sotto app/.verification-smoke."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parent / ".verification-smoke"
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        work = Path(temporary)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
            env[key] = str(work / key)

        def run(*args, json_output=True):
            result = subprocess.run(
                [sys.executable, "-B", "-m", "fad_downloader", "--no-log",
                 "--env-file", str(work / "absent.env"), "--database", str(work / "demo.sqlite3"),
                 *args],
                cwd=work, env=env, capture_output=True, text=True, check=True,
            )
            return json.loads(result.stdout) if json_output else result.stdout

        for user in ("studente1", "studente2"):
            workspace = str(work / user)
            prefix = ("--db-user", user)
            result = run(*prefix, "download", "--demo", "--workspace", workspace)
            assert len(result["results"]) == 3
            assert run("verify", "--workspace", workspace)["issues"] == []
            assert len(run(*prefix, "db-history", "--demo")) == 3
            pdf = work / (user + ".pdf")
            run(*prefix, "report-pdf", "--demo", "--output", str(pdf), json_output=False)
            assert pdf.read_bytes().startswith(b"%PDF")
        print("Smoke OK: due utenti, download, verifica integrita, storico e PDF personali.")


if __name__ == "__main__":
    main()
