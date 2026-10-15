from dataclasses import replace

import pytest

from fad_downloader.demo import DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import Account, Catalog, FadError, Limits, Naming
from fad_downloader.services import Downloader, alternate_tasks, plan, verify
from fad_downloader.state import (
    backup_state,
    load_catalog,
    load_pending,
    preferences,
    recovery_inventory,
    restore_state,
    save_catalog,
    save_pending,
    save_preferences,
)
from fad_downloader.storage import SafeRoot


def test_catalog_changes_and_account_isolation(tmp_path):
    found = catalog()
    changes = save_catalog(tmp_path, DEMO_ACCOUNT, found)
    assert len(changes["new"]) == 3
    loaded, _ = load_catalog(tmp_path, DEMO_ACCOUNT)
    assert loaded.resources == found.resources
    changed = Catalog(found.courses, [replace(found.resources[0], name="rinominato")])
    changes = save_catalog(tmp_path, DEMO_ACCOUNT, changed)
    assert changes["changed"] == [found.resources[0].id]
    assert len(changes["not_seen"]) == 2
    with pytest.raises(FadError, match="altro account"):
        load_catalog(tmp_path, Account(DEMO_ACCOUNT.origin, "other"))


def test_removed_remote_preserves_materials_and_marks_unknown_if_partial(tmp_path):
    found = catalog()
    tasks = plan(found.resources, tmp_path, DEMO_ACCOUNT, Naming())
    Downloader(DemoHttp(), DEMO_ACCOUNT).run(tasks, tmp_path)
    save_catalog(tmp_path, DEMO_ACCOUNT, found)
    save_catalog(tmp_path, DEMO_ACCOUNT, Catalog(warnings=["parziale"]))
    root = SafeRoot(tmp_path)
    assert all(
        r["remote_state"] == "non_verificato"
        for r in root.json(".fad/manifest.json")["records"].values()
    )
    save_catalog(tmp_path, DEMO_ACCOUNT, Catalog())
    assert all(
        r["remote_state"] == "non_più_visibile"
        for r in root.json(".fad/manifest.json")["records"].values()
    )
    assert not verify(tmp_path)["issues"]


def test_catalog_strips_secret_query(tmp_path):
    found = catalog()
    resource = replace(
        found.resources[0], url=found.resources[0].url + "?token=SECRET&forcedownload=1"
    )
    save_catalog(tmp_path, DEMO_ACCOUNT, Catalog(found.courses, [resource]))
    assert "SECRET" not in (tmp_path / ".fad/catalog.json").read_text()


def test_pending_recovered_and_wrong_account_rejected(tmp_path):
    tasks = plan(catalog().resources, tmp_path, DEMO_ACCOUNT, Naming())
    save_pending(tmp_path, DEMO_ACCOUNT, tasks)
    assert load_pending(tmp_path, DEMO_ACCOUNT) == tasks
    with pytest.raises(FadError):
        load_pending(tmp_path, Account(DEMO_ACCOUNT.origin, "other"))


def test_backup_restore_and_inventory(tmp_path):
    save_catalog(tmp_path, DEMO_ACCOUNT, catalog())
    folder = backup_state(tmp_path)
    save_catalog(tmp_path, DEMO_ACCOUNT, Catalog())
    restore_state(tmp_path, folder)
    assert len(load_catalog(tmp_path)[0].resources) == 3
    inventory = recovery_inventory(tmp_path)
    assert folder in inventory["backups"]
    with pytest.raises(FadError):
        restore_state(tmp_path, "../outside")


def test_global_preferences_and_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_preferences(tmp_path / "workspace", Naming(), Limits(file_bytes=123))
    assert preferences()["limits"]["file_bytes"] == 123
    with pytest.raises(FadError):
        Limits(file_bytes=-1)
    with pytest.raises(FadError):
        Limits(timeout=1000)


def test_subfolder_and_extended_naming(tmp_path):
    resource = replace(
        catalog().resources[0],
        subfolder="Pratica/Esercizi",
        section_index=2,
        activity_name="Allegati",
    )
    task = plan(
        [resource], tmp_path, DEMO_ACCOUNT, Naming(section="{section_index}_{section_name}")
    )[0]
    assert "/2_Introduzione/Materiali/1_Allegati/Pratica/Esercizi/" in task.relative
    with pytest.raises(FadError):
        plan([replace(resource, subfolder="../escape")], tmp_path, DEMO_ACCOUNT, Naming())


def test_alternative_copy_preserves_modified_file(tmp_path):
    tasks = plan(catalog().resources[:1], tmp_path, DEMO_ACCOUNT, Naming())
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    downloader.run(tasks, tmp_path)
    local = tmp_path / tasks[0].relative
    local.write_bytes(b"mio lavoro")
    assert downloader.run(tasks, tmp_path)["counts"] == {"conflitto": 1}
    copies = alternate_tasks(tmp_path, DEMO_ACCOUNT)
    assert copies[0].relative != tasks[0].relative
    assert downloader.run(copies, tmp_path)["counts"] == {"scaricato": 1}
    assert local.read_bytes() == b"mio lavoro"


def test_one_reauthentication_and_same_account_required(tmp_path):
    class Expired(DemoHttp):
        def __init__(self):
            super().__init__()
            self.expired = True

        def request(self, *args, **kwargs):
            if self.expired:
                raise FadError("AUTH_REQUIRED", "scaduta")
            return super().request(*args, **kwargs)

    client = Expired()
    calls = []

    def login():
        calls.append(True)
        client.expired = False
        return DEMO_ACCOUNT

    tasks = plan(catalog().resources[:1], tmp_path, DEMO_ACCOUNT, Naming())
    result = Downloader(client, DEMO_ACCOUNT, login).run(tasks, tmp_path)
    assert result["counts"] == {"scaricato": 1}
    assert len(calls) == 1
    other = tmp_path / "other"
    tasks = plan(catalog().resources[:1], other, DEMO_ACCOUNT, Naming())
    result = Downloader(Expired(), DEMO_ACCOUNT, lambda: Account(DEMO_ACCOUNT.origin, "other")).run(
        tasks, other
    )
    assert result["counts"] == {"fallito": 1}
    assert len(load_pending(other, DEMO_ACCOUNT)) == 1


def test_restore_corrupt_manifest_and_preserve_raw_evidence(tmp_path):
    save_catalog(tmp_path, DEMO_ACCOUNT, catalog())
    folder = backup_state(tmp_path)
    (tmp_path / ".fad/manifest.json").write_bytes(b"{corrupt")
    assert folder in recovery_inventory(tmp_path)["backups"]
    restore_state(tmp_path, folder)
    assert len(load_catalog(tmp_path)[0].resources) == 3
    backups = recovery_inventory(tmp_path)["backups"]
    assert any((tmp_path / path / "manifest.json").read_bytes() == b"{corrupt" for path in backups)


def test_future_schema_is_not_automatically_replaced(tmp_path):
    save_catalog(tmp_path, DEMO_ACCOUNT, catalog())
    folder = backup_state(tmp_path)
    SafeRoot(tmp_path).write_json(
        ".fad/manifest.json", {"version": 99, "account": DEMO_ACCOUNT.key, "records": {}}
    )
    with pytest.raises(FadError, match="futuro"):
        restore_state(tmp_path, folder)


def test_recovery_identifies_only_application_temporaries(tmp_path):
    save_catalog(tmp_path, DEMO_ACCOUNT, catalog())
    name = ".part-" + "a" * 32
    (tmp_path / name).write_bytes(b"unfinished")
    (tmp_path / "user.tmp").write_bytes(b"user")
    assert recovery_inventory(tmp_path)["temporary_files"] == [name]


def test_totals_separate_resources_and_files(tmp_path):
    tasks = plan(catalog().resources, tmp_path, DEMO_ACCOUNT, Naming())
    report = Downloader(DemoHttp(), DEMO_ACCOUNT).run(tasks, tmp_path)
    assert report["resources"] == 3
    assert report["files"] == 3
    assert not report["partial"]
