from dataclasses import replace
import json
from unittest.mock import Mock

from bs4 import BeautifulSoup
import pytest

from fad_downloader.demo import DEMO_ACCOUNT, DemoHttp, catalog
from fad_downloader.domain import Course, FadError, ORIGIN, Section
from fad_downloader.moodle import Moodle
from fad_downloader.network import HttpClient
from fad_downloader.state import load_catalog, save_catalog


def initial_html(course_id="1"):
    config = json.dumps({"id": course_id, "contextid": 10, "partialrender": True})
    return f"""<script>snap.snapInit({config}, true);</script>
    <ol id="chapters" class="chapters">
    <li><a class="chapter-title" href="#section-0">Generale</a></li>
    <li><a class="chapter-title" href="#section-1">Lezioni</a></li>
    <li><a class="chapter-title" href="#section-1">Lezioni</a></li>
    <li><a class="chapter-title" href="#section-2">Sezione vuota</a></li></ol>
    <li class="section" id="section-0"><h2 class="sectionname">Generale</h2></li>"""


def test_snap_loads_all_visible_sections_once_including_empty():
    moodle = Moodle(DemoHttp())
    course = Course(1, "C", ORIGIN + "/course/view.php?id=1")
    moodle.page = Mock(return_value=(BeautifulSoup(initial_html(), "html.parser"), course.url))
    calls = []

    def ajax(method, args):
        if method == "core_course_get_contents":
            return None
        number = dict((v["name"], v["value"]) for v in args["args"])["section"]
        calls.append(number)
        activity = '<a href="/mod/page/view.php?id=7">Lezione</a>' if number == "1" else ""
        return {
            "html": f'<li class="section" id="section-{number}"><h2 class="sectionname">Titolo</h2>{activity}</li>',
            "javascript": "DO_NOT_EXECUTE",
        }

    moodle.ajax = ajax
    resources = moodle.activities(course)
    assert calls == ["1", "2"]
    assert len(moodle.sections) == 3
    assert all(s.available for s in moodle.sections.values())
    assert len(resources) == 1
    assert resources[0].section == "Lezioni"
    assert resources[0].section_id == "1"
    assert resources[0].section_index == 1
    assert not moodle.warnings


def test_failed_section_does_not_hide_other_sections():
    moodle = Moodle(DemoHttp())
    course = Course(1, "C", ORIGIN + "/course/view.php?id=1")

    def ajax(method, args):
        number = args["args"][1]["value"]
        if number == "1":
            raise FadError("ACCESS_DENIED", "non disponibile")
        return {"html": f'<li class="section" id="section-{number}"></li>'}

    moodle.ajax = ajax
    result = moodle.snap_sections(course, BeautifulSoup(initial_html(), "html.parser"))
    assert result.select_one("#section-2")
    assert not moodle.sections[(1, 1)].available
    assert moodle.sections[(1, 2)].available
    assert moodle.warnings


def test_catalog_keeps_empty_sections_and_equal_titles(tmp_path):
    found = catalog()
    found.sections = [Section("1", 1, "Uguale", 1), Section("2", 1, "Uguale", 2)]
    found.resources = [replace(found.resources[0], section_id="1", section="Uguale")]
    save_catalog(tmp_path, DEMO_ACCOUNT, found)
    loaded, _ = load_catalog(tmp_path, DEMO_ACCOUNT)
    assert loaded.sections == found.sections


@pytest.mark.parametrize(
    "change",
    [
        {"component": "other"},
        {"callback": "delete"},
        {"contextid": 0},
        {"args": [{"name": "courseid", "value": "1"}, {"name": "delete", "value": "1"}]},
    ],
)
def test_fragment_requests_are_restricted_to_snap_read_callback(change):
    client = HttpClient()
    args = {
        "component": "theme_snap",
        "callback": "section",
        "contextid": 10,
        "args": [{"name": "courseid", "value": "1"}, {"name": "section", "value": "2"}],
    }
    args.update(change)
    client.session.request = Mock()
    with pytest.raises(FadError):
        client.request(
            ORIGIN + "/lib/ajax/service.php",
            "POST",
            json=[{"methodname": "core_get_fragment", "args": args}],
        )
    client.session.request.assert_not_called()
    client.close()
