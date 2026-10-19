from dataclasses import replace

import pytest
from pypdf import PdfReader

from fad_downloader.database import Archive
from fad_downloader.demo import DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import FadError, Naming, Result
from fad_downloader.pdf_reports import export_user_report
from fad_downloader.services import Downloader, plan
from fad_downloader.storage import SafeRoot


def text(path):
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


def test_pdf_includes_only_authenticated_users_downloads(tmp_path):
    archive = Archive(tmp_path / "archive.sqlite3")
    archive.register("alice", "AlicePassword!")
    archive.register("bob", "BobPassword!")
    alice = archive.login("alice", "AlicePassword!")
    bob = archive.login("bob", "BobPassword!")
    resource = replace(catalog().resources[0], name="Documento privato di Alice")
    workspace = tmp_path / "work"
    Downloader(DemoHttp(), DEMO_ACCOUNT, archive=archive, user_session=alice).run(
        plan([resource], workspace, DEMO_ACCOUNT, Naming()), workspace
    )
    export_user_report(archive, alice, tmp_path / "alice.pdf")
    export_user_report(archive, bob, tmp_path / "bob.pdf")
    assert "Documento privato di Alice" in text(tmp_path / "alice.pdf")
    assert "Documento privato di Alice" not in text(tmp_path / "bob.pdf")
    assert "Nessun download" in text(tmp_path / "bob.pdf")
    assert "AlicePassword!" not in text(tmp_path / "alice.pdf")


def test_pdf_pagination_escape_and_no_overwrite(tmp_path):
    archive = Archive(tmp_path / "archive.sqlite3", demo=True)
    session = archive.demo_session()
    run = archive.start_run(session, DEMO_ACCOUNT)
    resource = catalog().resources[0]
    for n in range(80):
        item = replace(resource, name=f"Risorsa {n} <b>test</b> & accenti \u00e8")
        archive.record(
            session, run, item, Result(item.id, item.name, "fallito"), SafeRoot(tmp_path)
        )
    export_user_report(archive, session, tmp_path / "report.pdf")
    reader = PdfReader(tmp_path / "report.pdf")
    assert len(reader.pages) > 1
    content = text(tmp_path / "report.pdf")
    assert "Risorsa 0" in content and "Risorsa 79" in content
    assert "<b>test</b>" in content
    assert all("Data UTC" in page.extract_text() for page in reader.pages)
    original = (tmp_path / "report.pdf").read_bytes()
    with pytest.raises(FadError):
        export_user_report(archive, session, tmp_path / "report.pdf")
    assert (tmp_path / "report.pdf").read_bytes() == original


def test_revoked_user_session_cannot_generate_report(tmp_path):
    archive = Archive(tmp_path / "demo.sqlite3", demo=True)
    session = archive.demo_session()
    archive.logout(session)
    with pytest.raises(FadError):
        export_user_report(archive, session, tmp_path / "forbidden.pdf")
    assert not (tmp_path / "forbidden.pdf").exists()
