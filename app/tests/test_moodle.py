from threading import Event
from unittest.mock import Mock

from bs4 import BeautifulSoup
import pytest

from fad_downloader.domain import Course, FadError, ORIGIN
from fad_downloader.moodle import Moodle, soup_document


def test_assignment_expands_material_submission_and_feedback_without_write():
    moodle = Moodle(Mock(cancel=Event()))
    course = Course(1, "Course", ORIGIN + "/course/view.php?id=1")
    resource = moodle.resource(course, 7, "Task", "assign", ORIGIN + "/mod/assign/view.php?id=7")
    markup = '''<a href="/pluginfile.php/9/outside.pdf">Outside</a><main id="region-main">
      <a href="/pluginfile.php/1/mod_assign/intro/task.pdf?time=123">Material</a>
      <a href="/pluginfile.php/2/assignsubmission_file/submission_files/answer.zip">Submission</a>
      <a href="/pluginfile.php/3/assignfeedback_editpdf/download/correction.pdf">Feedback</a>
      <a href="/mod/assign/view.php?id=7&action=editsubmission">Edit</a>
      <a href="https://evil.test/pluginfile.php/4/stolen.pdf">External</a>
      <a href="/pluginfile.php/1/mod_assign/intro/task.pdf?time=123">Duplicate</a>
    </main>'''
    moodle.page = Mock(return_value=(BeautifulSoup(markup, "html.parser"), resource.url))
    result = moodle.expand(course, resource)
    assert result[0] is resource
    assert [r.name for r in result[1:]] == ["task.pdf", "answer.zip", "correction.pdf"]
    assert all(r.kind == "file" and r.activity_id == 7 for r in result[1:])
    moodle.page.assert_called_once_with(resource.url)


def test_assignment_unknown_layout_keeps_activity_and_warns():
    moodle = Moodle(Mock(cancel=Event()))
    course = Course(1, "Course", ORIGIN + "/course/view.php?id=1")
    resource = moodle.resource(course, 7, "Task", "assign", ORIGIN + "/mod/assign/view.php?id=7")
    moodle.page = Mock(return_value=(BeautifulSoup("<html></html>", "html.parser"), resource.url))
    assert moodle.expand(course, resource) == [resource]
    assert moodle.warnings


def test_scan_publishes_courses_before_loading_and_independent_snapshots():
    from fad_downloader.demo import catalog
    from fad_downloader.domain import Limits

    demo = catalog()
    moodle = Moodle(Mock(cancel=Event(), limits=Limits()))
    moodle.courses = Mock(return_value=demo.courses)
    snapshots = []

    def activities(course):
        assert len(snapshots) == 1
        assert snapshots[0].courses == demo.courses
        assert not snapshots[0].resources
        return demo.resources

    moodle.activities = activities
    moodle.expand = lambda course, resource: [resource]
    result = moodle.scan(progress=snapshots.append)
    assert len(snapshots) == 2
    assert not snapshots[0].resources
    assert snapshots[1].resources == result.resources == demo.resources
    result.resources.clear()
    assert len(snapshots[1].resources) == 3


def test_login_html_is_not_authenticated():
    with pytest.raises(FadError, match="Sessione"):
        soup_document('<html><input name="logintoken" value="x"></html>', ORIGIN + "/my/")


def test_unavailable_course_response_is_not_an_empty_resource():
    markup = '<body id="page-mod-resource-view"><main id="region-main">Questo corso al momento non è disponibile agli studenti. Continua</main></body>'
    with pytest.raises(FadError) as failure:
        soup_document(markup, ORIGIN + '/mod/resource/view.php?id=1')
    assert failure.value.code == 'COURSE_UNAVAILABLE'
    assert soup_document(markup.replace('page-mod-resource-view', 'page-mod-quiz-review'), ORIGIN + '/mod/quiz/review.php?attempt=1')


def test_scan_ignores_unavailable_course_links_but_keeps_other_errors():
    from fad_downloader.domain import Limits

    moodle = Moodle(Mock(cancel=Event(), limits=Limits()))
    course = Course(1, "Course", ORIGIN + '/course/view.php?id=1')
    blocked, denied, available = [
        moodle.resource(course, mid, name, 'resource', ORIGIN + f'/mod/resource/view.php?id={mid}')
        for mid, name in ((1, 'Unavailable'), (2, 'Other error'), (3, 'Available'))
    ]
    moodle.courses = Mock(return_value=[course])
    moodle.activities = Mock(return_value=[blocked, denied, available])

    def expand(_, resource):
        if resource is blocked:
            soup_document('<body id="page-mod-resource-view"><main id="region-main">Questo corso al momento non è disponibile agli studenti. Continua</main></body>', resource.url)
        if resource is denied:
            raise FadError('ACCESS_DENIED', 'Errore di accesso distinto.')
        return [resource]

    moodle.expand = expand
    result = moodle.scan()
    assert result.resources == [available]
    assert len(result.warnings) == 1
    assert 'Errore di accesso distinto.' in result.warnings[0]
    assert 'Unavailable' not in result.warnings[0]


def test_ignored_resource_is_reconsidered_on_the_next_scan():
    from fad_downloader.domain import Limits

    moodle = Moodle(Mock(cancel=Event(), limits=Limits()))
    course = Course(1, "Course", ORIGIN + '/course/view.php?id=1')
    resource = moodle.resource(course, 7, 'Material', 'resource', ORIGIN + '/mod/resource/view.php?id=7')
    moodle.courses = Mock(return_value=[course])
    moodle.activities = Mock(return_value=[resource])
    moodle.expand = Mock(side_effect=[FadError('COURSE_UNAVAILABLE', 'Non disponibile.'), [resource]])
    first = moodle.scan()
    assert first.resources == [] and first.warnings == []
    second = moodle.scan()
    assert second.resources == [resource] and second.warnings == []


def test_real_html_attachment_is_classified_for_passive_export():
    from contextlib import nullcontext
    moodle = Moodle(Mock(cancel=Event()))
    course = Course(1, "C", ORIGIN + '/course/view.php?id=1')
    resource = moodle.resource(course, 7, 'HTML lesson', 'resource', ORIGIN + '/mod/resource/view.php?id=7')
    response = Mock(headers={'Content-Type':'text/html'}, url=ORIGIN+'/pluginfile.php/12/mod_resource/content/1/lesson.html')
    moodle.http.request.return_value = nullcontext(response)
    moodle.http.chunks.return_value = iter([b'<html><body><h1>Lesson</h1></body></html>'])
    result = moodle.expand(course, resource)
    assert len(result) == 1 and result[0].kind == 'page'
    assert result[0].url == response.url and result[0].activity_id == 7


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


@pytest.mark.parametrize("attempt_column", [True, False])
def test_quiz_state_column_follows_table_header(attempt_column):
    moodle = Moodle(Mock(cancel=Event()))
    prefix = "<th>Tentativo</th>" if attempt_column else ""
    cell = '<td class="cell c0">1</td>' if attempt_column else ""
    markup = (
        f"<table><thead><tr>{prefix}<th>Stato</th><th>Valutazione</th><th>Revisione</th></tr></thead>"
        f"<tbody><tr>{cell}<td>Terminato</td><td>30</td>"
        '<td><a href="/mod/quiz/review.php?attempt=2">Revisione</a></td></tr>'
        f"<tr>{cell}<td>In corso</td><td></td>"
        '<td><a href="/mod/quiz/review.php?attempt=3">Revisione</a></td></tr></tbody></table>'
    )
    moodle.page = Mock(return_value=(BeautifulSoup(markup, "html.parser"), ORIGIN))
    course = Course(1, "Corso", ORIGIN + "/course/view.php?id=1")
    quiz = moodle.resource(course, 1, "Verifica", "quiz", ORIGIN + "/mod/quiz/view.php?id=1")
    result = moodle.expand(course, quiz)
    assert [r.attempt_id for r in result] == ["2"]


def test_folder_subdirectories():
    assert (
        Moodle.folder_path(ORIGIN + "/pluginfile.php/5/mod_folder/content/0/uno/due/file.txt")
        == "uno/due"
    )
