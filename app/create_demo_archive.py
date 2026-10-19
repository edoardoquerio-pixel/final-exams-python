"""Esempio riproducibile offline: due utenti DB, BLOB e report PDF a più pagine."""

from dataclasses import replace
from pathlib import Path

from fad_downloader.database import Archive
from fad_downloader.demo import DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import Naming, identifier
from fad_downloader.pdf_reports import export_user_report
from fad_downloader.services import Downloader, plan


def main():
    project = Path(__file__).resolve().parent
    base = project / "demo-database"
    base.mkdir(exist_ok=True)
    archive = Archive(base / "demo.sqlite3", demo=True)
    session = archive.demo_session()
    for username, password in (("studente1", "DemoStudente1!"), ("studente2", "DemoStudente2!")):
        archive.logout(session)
        session = archive.login(username, password)
        resources = catalog().resources
        if username == "studente1":
            resources = resources + [
                replace(
                    resources[0],
                    id=identifier("example:" + str(n)),
                    activity_id=100 + n,
                    name=f"Esercizio di riepilogo {n:02d}.py",
                )
                for n in range(1, 19)
            ]
        workspace = base / username
        tasks = plan(resources, workspace, DEMO_ACCOUNT, Naming())
        Downloader(DemoHttp(), DEMO_ACCOUNT, archive=archive, user_session=session).run(
            tasks, workspace
        )
    archive.logout(session)
    session = archive.login("studente1", "DemoStudente1!")
    examples = project / "examples"
    examples.mkdir(exist_ok=True)
    path = export_user_report(archive, session, examples / "report_download_studente1.pdf")
    archive.logout(session)
    print(path)


if __name__ == "__main__":
    main()
