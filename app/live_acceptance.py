"""Collaudo FAD reale in sola lettura. Eseguire solo con autorizzazione esplicita."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

from fad_downloader.database import Archive
from fad_downloader.domain import FadError, Naming, SUPPORTED_RESOURCE_KINDS
from fad_downloader.env_config import read_credentials
from fad_downloader.moodle import Moodle
from fad_downloader.network import HttpClient
from fad_downloader.observability import configure
from fad_downloader.pdf_reports import export_user_report
from fad_downloader.services import Downloader, plan, verify
from fad_downloader.state import save_catalog


def main():
    app = Path(__file__).resolve().parent
    run = app / ".verification-live" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + secrets.token_hex(3))
    run.mkdir(parents=True, mode=0o700)
    configure(enabled=False)
    moodle = Moodle(HttpClient())
    summary = {"stage": "login", "all_accessible_courses": True}
    archive = session = None

    def record():
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary), flush=True)

    try:
        username, password = read_credentials(app / ".env")
        if not username or not password:
            raise FadError("AUTH_REQUIRED", "Credenziali mancanti")
        account = moodle.login(username, password)
        password = None
        summary["stage"] = "scan"
        record()
        found = moodle.scan(progress=lambda catalog: print(json.dumps({"scan_courses": len(catalog.courses), "scan_resources": len(catalog.resources)}), flush=True))
        resources = [r for r in found.resources if r.kind in SUPPORTED_RESOURCE_KINDS]
        summary.update(courses=len(found.courses), sections=len(found.sections), resources=len(found.resources),
                       warnings=len(found.warnings), supported=len(resources),
                       unsupported=len(found.resources) - len(resources), stage="download")
        record()
        workspace = run / "workspace"
        save_catalog(workspace, account, found)
        tasks = plan(resources, workspace, account, Naming())
        archive = Archive(run / "archive.sqlite3")
        local_password = secrets.token_urlsafe(32)
        archive.register("collaudo_locale", local_password)
        session = archive.login("collaudo_locale", local_password)
        local_password = None
        completed = 0

        def progress(_):
            nonlocal completed
            completed += 1
            print(json.dumps({"task_events": completed}), flush=True)

        def reauthenticate():
            user, secret = read_credentials(app / ".env")
            return moodle.login(user, secret)

        downloader = Downloader(moodle.http, account, reauthenticate, archive, session)
        first = downloader.run(tasks, workspace, emit=progress)
        summary.update(first_counts=first["counts"], first_error_codes=dict(Counter(r.get("code", "") for r in first["results"] if r.get("code"))), stage="incremental")
        record()
        second = downloader.run(tasks, workspace, emit=progress)
        summary.update(second_counts=second["counts"], integrity=verify(workspace), stage="pdf")
        # The detailed report stays local: do not print private titles or paths.
        summary["integrity"] = {"checked": summary["integrity"]["checked"], "issues": len(summary["integrity"]["issues"])}
        export_user_report(archive, session, run / "report.pdf")
        with archive.connect() as database:
            summary["sqlite_integrity"] = database.execute("PRAGMA integrity_check").fetchone()[0]
        summary["history_rows"] = len(archive.history(session))
        summary["stage"] = "complete"
        record()
        failed = {"fallito", "conflitto", "annullato", "archiviazione_fallita"}
        return int(bool(found.warnings or summary["integrity"]["issues"] or any(first["counts"].get(k, 0) or second["counts"].get(k, 0) for k in failed)))
    except Exception as exc:
        summary.update(stage="failed", error_code=exc.code if isinstance(exc, FadError) else type(exc).__name__)
        record()
        return 1
    finally:
        if archive and session:
            archive.logout(session)
        try:
            moodle.logout()
        except Exception:
            moodle.close()


if __name__ == "__main__":
    raise SystemExit(main())
