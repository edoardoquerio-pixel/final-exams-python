from dataclasses import replace
import json
from unittest.mock import Mock

import pytest

from fad_downloader.demo import DATA, DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import Account, FadError, Naming, ORIGIN
from fad_downloader.services import Downloader, load_settings, plan, save_settings, verify
from fad_downloader.storage import SafeRoot, load_manifest


def demo_tasks(workspace):
    return plan(catalog().resources, workspace, DEMO_ACCOUNT, Naming())


def test_plan_does_not_write(tmp_path):
    workspace = tmp_path / "not-created"
    tasks = demo_tasks(workspace)
    assert len(tasks) == 3
    assert not workspace.exists()
    assert len({t.relative for t in tasks}) == 3


def test_end_to_end_demo_and_independent_verify(tmp_path):
    report = Downloader(DemoHttp(), DEMO_ACCOUNT).run(demo_tasks(tmp_path), tmp_path)
    assert report["counts"] == {"scaricato": 3}
    assert verify(tmp_path) == {"checked": 3, "issues": []}
    manifest = load_manifest(SafeRoot(tmp_path), DEMO_ACCOUNT)
    quiz = next(r for r in manifest["records"].values() if r["kind"] == "quiz_review")
    html = (tmp_path / quiz["path"]).read_text(encoding="utf-8")
    assert "[selezionata]" in html
    assert "NON_ESPORTARE" not in html
    assert "<input" not in html
    assert (tmp_path / ".fad/index.html").is_file()


def test_user_modifications_preserved(tmp_path):
    tasks = demo_tasks(tmp_path)[:1]
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    downloader.run(tasks, tmp_path)
    path = tmp_path / tasks[0].relative
    path.write_bytes(b"my edits")
    report = downloader.run(tasks, tmp_path)
    assert report["counts"] == {"conflitto": 1}
    assert path.read_bytes() == b"my edits"
    assert verify(tmp_path)["issues"]


def test_missing_file_redownloaded(tmp_path):
    tasks = demo_tasks(tmp_path)[:1]
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    downloader.run(tasks, tmp_path)
    (tmp_path / tasks[0].relative).unlink()
    report = downloader.run(tasks, tmp_path)
    assert report["counts"] == {"aggiornato": 1}
    assert (tmp_path / tasks[0].relative).read_bytes() == DATA


def test_wrong_size_never_committed(tmp_path):
    resource = replace(catalog().resources[0], size=999)
    tasks = plan([resource], tmp_path, DEMO_ACCOUNT, Naming())
    report = Downloader(DemoHttp(), DEMO_ACCOUNT).run(tasks, tmp_path)
    assert report["counts"] == {"fallito": 1}
    assert not (tmp_path / tasks[0].relative).exists()
    assert not load_manifest(SafeRoot(tmp_path))["records"]


def test_html_login_not_downloaded(tmp_path):
    http = DemoHttp()
    http.chunks = lambda response, limit=None: iter([b"<html>login</html>"])
    report = Downloader(http, DEMO_ACCOUNT).run(demo_tasks(tmp_path)[:1], tmp_path)
    assert report["counts"] == {"fallito": 1}


def test_cancel_gives_result_for_every_task(tmp_path):
    http = DemoHttp()
    http.cancel.set()
    report = Downloader(http, DEMO_ACCOUNT).run(demo_tasks(tmp_path), tmp_path)
    assert report["counts"] == {"annullato": 3}


def test_atomic_export_keeps_previous_generation(tmp_path):
    tasks = demo_tasks(tmp_path)[1:2]
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    downloader.run(tasks, tmp_path)
    original = (tmp_path / ".fad/manifest.json").read_bytes()
    downloader.http.document = Mock(side_effect=FadError("NETWORK", "interrotto"))
    report = downloader.run(tasks, tmp_path)
    assert report["counts"] == {"fallito": 1}
    assert (tmp_path / ".fad/manifest.json").read_bytes() == original
    assert verify(tmp_path)["issues"] == []


def test_mapping_and_existing_path_stability(tmp_path):
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    tasks = demo_tasks(tmp_path)
    downloader.run(tasks, tmp_path)
    changed = plan(catalog().resources, tmp_path, DEMO_ACCOUNT, Naming(course="Changed"))
    assert [t.relative for t in changed] == [t.relative for t in tasks]
    save_settings(tmp_path, DEMO_ACCOUNT, Naming(), {"1": "Corso_personale"})
    assert load_settings(tmp_path)[1] == {"1": "Corso_personale"}
    with pytest.raises(FadError):
        save_settings(tmp_path, Account(ORIGIN, "another"), Naming(), {})


def test_new_unknown_file_not_overwritten(tmp_path):
    task = demo_tasks(tmp_path)[0]
    path = tmp_path / task.relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"unknown")
    result = Downloader(DemoHttp(), DEMO_ACCOUNT).run([task], tmp_path)
    assert result["counts"] == {"conflitto": 1}
    assert path.read_bytes() == b"unknown"


def test_304_requires_verified_copy(tmp_path):
    task = demo_tasks(tmp_path)[0]
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    downloader.run([task], tmp_path)
    original_request = downloader.http.request

    def unchanged(url, **kwargs):
        response = original_request(url)
        response.status_code = 304
        return response

    downloader.http.request = unchanged
    report = downloader.run([task], tmp_path)
    assert report["counts"] == {"invariato": 1}
    (tmp_path / task.relative).unlink()
    report = downloader.run([task], tmp_path)
    assert report["counts"] == {"fallito": 1}


def test_reports_contain_no_url_tokens(tmp_path):
    resource = replace(catalog().resources[0], url=ORIGIN + "/pluginfile.php/1/file?token=SENTINEL")
    Downloader(DemoHttp(), DEMO_ACCOUNT).run(
        plan([resource], tmp_path, DEMO_ACCOUNT, Naming()), tmp_path
    )
    for path in (tmp_path / ".fad").glob("*.json"):
        assert "SENTINEL" not in path.read_text()
        json.loads(path.read_text())



def test_304_detects_local_edit_during_request(tmp_path):
    task = demo_tasks(tmp_path)[0]
    downloader = Downloader(DemoHttp(), DEMO_ACCOUNT)
    assert downloader.run([task], tmp_path)["counts"] == {"scaricato": 1}
    original_request = downloader.http.request
    local = tmp_path / task.relative

    def unchanged(url, **kwargs):
        local.write_bytes(b"local edit")
        response = original_request(url)
        response.status_code = 304
        return response

    downloader.http.request = unchanged
    assert downloader.run([task], tmp_path)["counts"] == {"conflitto": 1}
    assert local.read_bytes() == b"local edit"
