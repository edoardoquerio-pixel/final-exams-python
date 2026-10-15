from threading import Event
from unittest.mock import Mock

from bs4 import BeautifulSoup
import pytest

from fad_downloader.domain import Course, FadError, ORIGIN
from fad_downloader.moodle import Moodle, soup_document


def test_login_html_is_not_authenticated():
    with pytest.raises(FadError, match="Sessione"):
        soup_document('<html><input name="logintoken" value="x"></html>', ORIGIN + "/my/")


def test_courses_pagination():
    moodle = Moodle(Mock(cancel=Event()))
    moodle.ajax = Mock(
        side_effect=[
            {"courses": [{"id": i, "fullname": str(i)} for i in range(1, 101)]},
            {"courses": [{"id": 101, "fullname": "last"}]},
        ]
    )
    courses = moodle.courses()
    assert len(courses) == 101
    assert moodle.ajax.call_args_list[1].args[1]["offset"] == 100


def test_html_fallback_dispatches_types_and_marks_partial():
    moodle = Moodle(Mock(cancel=Event()))
    moodle.ajax = Mock(return_value=None)
    markup = '<a href="/mod/page/view.php?id=2">Page</a><a href="/mod/folder/view.php?id=3">Folder</a><a href="/mod/assign/view.php?id=4">Assignment</a>'
    moodle.page = Mock(return_value=(BeautifulSoup(markup, "html.parser"), ORIGIN))
    resources = moodle.activities(Course(1, "C", ORIGIN + "/course/view.php?id=1"))
    assert {r.kind for r in resources} == {"page", "folder", "assign"}
    assert moodle.warnings


def test_quiz_only_finished_attempts():
    moodle = Moodle(Mock(cancel=Event()))
    markup = '<table><tr><td class="state">Terminato</td><td><a href="/mod/quiz/review.php?attempt=2">Review</a></td></tr><tr><td class="state">In corso</td><td><a href="/mod/quiz/review.php?attempt=3">Review</a></td></tr></table>'
    moodle.page = Mock(return_value=(BeautifulSoup(markup, "html.parser"), ORIGIN))
    course = Course(1, "C", ORIGIN + "/course/view.php?id=1")
    quiz = moodle.resource(course, 3, "Quiz", "quiz", ORIGIN + "/mod/quiz/view.php?id=3")
    result = moodle.expand(course, quiz)
    assert len(result) == 1
    assert "attempt=2" in result[0].url


def test_quiz_identity_independent_of_pagination():
    moodle = Moodle(Mock(cancel=Event()))
    course = Course(1, "C", ORIGIN + "/course/view.php?id=1")
    first = moodle.resource(
        course, 1, "Quiz", "quiz_review", ORIGIN + "/mod/quiz/review.php?attempt=2&page=0"
    )
    second = moodle.resource(
        course, 1, "Quiz", "quiz_review", ORIGIN + "/mod/quiz/review.php?attempt=2&showall=1"
    )
    assert first.id == second.id


def test_folder_subdirectories():
    assert (
        Moodle.folder_path(ORIGIN + "/pluginfile.php/5/mod_folder/content/0/uno/due/file.txt")
        == "uno/due"
    )
