from dataclasses import replace

import pytest

from fad_downloader.database import Archive
from fad_downloader.demo import DATA, DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import FadError, Naming, Result
from fad_downloader.services import Downloader, plan
from fad_downloader.storage import SafeRoot


@pytest.fixture
def users(tmp_path):
    archive = Archive(tmp_path / "archive.sqlite3")
    archive.register("alice", "PasswordAlice!")
    archive.register("bob", "PasswordBob!")
    return archive, archive.login("alice", "PasswordAlice!"), archive.login("bob", "PasswordBob!")


def download(archive, session, workspace):
    tasks = plan(catalog().resources, workspace, DEMO_ACCOUNT, Naming())
    return Downloader(DemoHttp(), DEMO_ACCOUNT, archive=archive, user_session=session).run(
        tasks, workspace
    )


def test_two_ordinary_users_password_hashes_and_login(users):
    archive, alice, bob = users
    with archive.connect() as db:
        rows = db.execute("SELECT * FROM users").fetchall()
        assert len(rows) == 2
        assert "role" not in rows[0].keys()
        assert "admin" not in rows[0].keys()
        assert rows[0]["password_hash"] != b"PasswordAlice!"
        assert rows[0]["salt"] != rows[1]["salt"]
    for name, pw in (("alice", "wrong"), ("missing", "wrong")):
        with pytest.raises(FadError, match="non valide"):
            archive.login(name, pw)
    archive.logout(alice)
    with pytest.raises(FadError):
        archive.history(alice)
    assert archive.history(bob) == []


def test_downloads_are_blob_objects_scoped_to_each_user(users, tmp_path):
    archive, alice, bob = users
    assert download(archive, alice, tmp_path / "alice")["counts"] == {"scaricato": 3}
    assert len(archive.history(alice)) == 3
    assert archive.history(bob) == []
    with archive.connect() as db:
        assert (
            db.execute("SELECT DISTINCT typeof(data) FROM object_chunks").fetchall()[0][0] == "blob"
        )
        assert db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 3
    assert download(archive, bob, tmp_path / "bob")["counts"] == {"scaricato": 3}
    assert len(archive.history(bob)) == 3
    assert len(archive.history(alice)) == 3


def test_foreign_user_cannot_restore_files_or_forge_session(users, tmp_path):
    archive, alice, bob = users
    download(archive, alice, tmp_path / "work")
    row = archive.history(alice)[0]
    object_id = archive.files(alice, row["id"])[0]["object_id"]
    assert archive.files(bob, row["id"]) == []
    with pytest.raises(FadError):
        archive.restore(bob, object_id, tmp_path / "foreign")
    with pytest.raises(FadError):
        archive.history(replace(alice, user_id=bob.user_id))
    with pytest.raises(FadError):
        archive.history(replace(alice, username="bob"))
    assert not (tmp_path / "foreign").exists()


def test_blob_survives_local_file_deletion_and_preserves_existing_destination(users, tmp_path):
    archive, alice, _ = users
    workspace = tmp_path / "work"
    download(archive, alice, workspace)
    row = next(r for r in archive.history(alice) if r["kind"] == "file")
    item = archive.files(alice, row["id"])[0]
    (workspace / item["relative_path"]).unlink()
    destination = tmp_path / "restored.py"
    archive.restore(alice, item["object_id"], destination)
    assert destination.read_bytes() == DATA
    with pytest.raises(FadError):
        archive.restore(alice, item["object_id"], destination)
    assert destination.read_bytes() == DATA


def test_corrupt_blob_never_commits_restored_file(users, tmp_path):
    archive, alice, _ = users
    download(archive, alice, tmp_path / "work")
    item = archive.files(alice, archive.history(alice)[0]["id"])[0]
    with archive.connect() as db:
        db.execute(
            "UPDATE object_chunks SET data=? WHERE object_id=?", (b"broken", item["object_id"])
        )
    with pytest.raises(FadError, match="corrotto"):
        archive.restore(alice, item["object_id"], tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_resource_and_assets_are_one_transaction(users, tmp_path):
    archive, alice, _ = users
    root = SafeRoot(tmp_path / "files", create=True)
    main_size, main_hash = root.write("index.html", [b"main"])
    asset_size, asset_hash = root.write("assets/file.txt", [b"asset"])
    resource = catalog().resources[0]
    record = {
        "path": "index.html",
        "size": main_size,
        "sha256": main_hash,
        "assets": [{"path": "assets/file.txt", "size": asset_size, "sha256": asset_hash}],
    }
    run_id = archive.start_run(alice, DEMO_ACCOUNT)
    archive.record(
        alice, run_id, resource, Result(resource.id, resource.name, "scaricato"), root, record
    )
    assert len(archive.files(alice, archive.history(alice)[0]["id"])) == 2
    record["assets"][0]["sha256"] = "0" * 64
    with pytest.raises(FadError):
        archive.record(
            alice, run_id, resource, Result(resource.id, resource.name, "scaricato"), root, record
        )
    assert len(archive.history(alice)) == 1


def test_large_object_is_chunked_without_size_limit_of_single_sqlite_blob(users, tmp_path):
    archive, alice, _ = users
    root = SafeRoot(tmp_path / "files", create=True)
    data = b"x" * (2 * 1024 * 1024 + 17)
    size, digest = root.write("large.bin", [data])
    resource = catalog().resources[0]
    run = archive.start_run(alice, DEMO_ACCOUNT)
    archive.record(
        alice,
        run,
        resource,
        Result(resource.id, resource.name, "scaricato"),
        root,
        {"path": "large.bin", "size": size, "sha256": digest},
    )
    with archive.connect() as db:
        sizes = [
            r[0] for r in db.execute("SELECT length(data) FROM object_chunks ORDER BY position")
        ]
    assert sizes == [1024 * 1024, 1024 * 1024, 17]


def test_sql_injection_and_foreign_run_are_rejected(users, tmp_path):
    archive, alice, bob = users
    with pytest.raises(FadError):
        archive.login("' OR 1=1 --", "password")
    with pytest.raises(FadError):
        archive.register("user'; DROP TABLE users; --", "password-long")
    run = archive.start_run(alice, DEMO_ACCOUNT)
    resource = catalog().resources[0]
    with pytest.raises(FadError):
        archive.record(
            bob, run, resource, Result(resource.id, resource.name, "fallito"), SafeRoot(tmp_path)
        )


def test_workspace_owner_and_demo_separation(users, tmp_path):
    archive, alice, bob = users
    download(archive, alice, tmp_path / "work")
    with pytest.raises(FadError, match="altro utente"):
        download(archive, bob, tmp_path / "work")
    with pytest.raises(FadError):
        archive.demo_session()
    with pytest.raises(FadError):
        Archive(archive.path, demo=True)
    demo = Archive(tmp_path / "demo.sqlite3", demo=True)
    session = demo.demo_session()
    from fad_downloader.domain import Account

    with pytest.raises(FadError):
        demo.start_run(session, Account(DEMO_ACCOUNT.origin, "real-user"))


def test_import_legacy_workspace_does_not_require_fad_login(users, tmp_path):
    archive, alice, _ = users
    workspace = tmp_path / "legacy"
    Downloader(DemoHttp(), DEMO_ACCOUNT).run(
        plan(catalog().resources, workspace, DEMO_ACCOUNT, Naming()), workspace
    )
    result = archive.import_workspace(alice, workspace)
    assert result["imported"] == 3
    assert result["failed"] == 0
    assert {r["status"] for r in archive.history(alice)} == {"importato"}


def test_failed_blob_archive_keeps_local_file_and_pending_task(users, tmp_path, monkeypatch):
    archive, alice, _ = users
    monkeypatch.setattr(
        archive, "record", lambda *a, **kw: (_ for _ in ()).throw(FadError("DB", "failed"))
    )
    workspace = tmp_path / "work"
    tasks = plan(catalog().resources[:1], workspace, DEMO_ACCOUNT, Naming())
    report = Downloader(DemoHttp(), DEMO_ACCOUNT, archive=archive, user_session=alice).run(
        tasks, workspace
    )
    assert report["counts"] == {"archiviazione_fallita": 1}
    assert (workspace / tasks[0].relative).read_bytes() == DATA
    assert SafeRoot(workspace).json(".fad/pending.json")["tasks"]
