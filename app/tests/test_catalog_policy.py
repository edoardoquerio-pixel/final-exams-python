from dataclasses import replace

import pytest

from fad_downloader.demo import DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import Catalog, FadError, Naming, ORIGIN
from fad_downloader.network import validate_url
from fad_downloader.services import Downloader, plan
from fad_downloader.state import load_catalog, save_catalog


def test_unsupported_activity_saved_but_not_requested(tmp_path):
    found = catalog()
    assignment = replace(
        found.resources[0], kind="assign", url=ORIGIN + "/mod/assign/view.php?id=17"
    )
    found.resources.append(assignment)
    save_catalog(tmp_path, DEMO_ACCOUNT, found)
    loaded, _ = load_catalog(tmp_path, DEMO_ACCOUNT)
    assert assignment in loaded.resources
    validate_url(assignment.url)  # Lettura allegati durante la scansione.
    with pytest.raises(FadError):
        validate_url(assignment.url, method="POST")
    client = DemoHttp()
    client.request = lambda *a, **kw: pytest.fail("Nessuna richiesta per attività non supportate")
    result = Downloader(client, DEMO_ACCOUNT).run(
        plan([assignment], tmp_path, DEMO_ACCOUNT, Naming()), tmp_path
    )
    assert result["counts"] == {"non_supportato": 1}


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/mod/assign/view.php?id=17",
        ORIGIN + "/mod/assign/view.php?id=17&delete=1",
        ORIGIN + "/mod/quiz/startattempt.php?id=17",
        ORIGIN + "/mod/assign/view.php?id=abc",
        ORIGIN + "/mod/assign/view.php?id=1&id=2",
    ],
)
def test_invalid_metadata_is_rejected_before_state_changes(tmp_path, url):
    original = catalog()
    save_catalog(tmp_path, DEMO_ACCOUNT, original)
    manifest = (tmp_path / ".fad/manifest.json").read_bytes()
    saved = (tmp_path / ".fad/catalog.json").read_bytes()
    invalid = replace(original.resources[0], kind="assign", url=url)
    with pytest.raises(FadError):
        save_catalog(tmp_path, DEMO_ACCOUNT, Catalog(resources=[invalid]))
    assert (tmp_path / ".fad/manifest.json").read_bytes() == manifest
    assert (tmp_path / ".fad/catalog.json").read_bytes() == saved


def test_moodle_url_activity_redirect_metadata(tmp_path):
    resource = replace(
        catalog().resources[0], kind="url", url=ORIGIN + "/mod/url/view.php?id=17&redirect=1"
    )
    save_catalog(tmp_path, DEMO_ACCOUNT, Catalog(resources=[resource]))
    assert load_catalog(tmp_path, DEMO_ACCOUNT)[0].resources == [resource]
    with pytest.raises(FadError):
        validate_url(resource.url)
    with pytest.raises(FadError):
        save_catalog(
            tmp_path,
            DEMO_ACCOUNT,
            Catalog(
                resources=[replace(resource, url=ORIGIN + "/mod/url/view.php?id=17&redirect=evil")]
            ),
        )
