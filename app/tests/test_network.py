import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from fad_downloader.domain import FadError, ORIGIN
from fad_downloader.network import HttpClient, PublicHTTPSConnection, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://fad.its-ictpiemonte.it/my/",
        "https://evil.test/my/",
        "https://user:pass@fad.its-ictpiemonte.it/my/",
        ORIGIN + ":444/my/",
        ORIGIN + "/mod/quiz/startattempt.php",
        ORIGIN + "/course/view.php?id=1&delete=1",
        ORIGIN + "/pluginfile.php/../secret",
        "file:///etc/passwd",
        ORIGIN + "/login/logout.php?sesskey=secret",
    ],
)
def test_reject_untrusted_url(url):
    with pytest.raises(FadError):
        validate_url(url)


def test_accept_read_routes():
    for url in (
        ORIGIN + "/my/",
        ORIGIN + "/mod/quiz/review.php?attempt=12&page=1",
        ORIGIN + "/pluginfile.php/1/x.pdf?forcedownload=1",
    ):
        validate_url(url)


def test_assignment_read_and_timestamp_file_only():
    validate_url(ORIGIN + "/mod/assign/view.php?id=17")
    validate_url(ORIGIN + "/pluginfile.php/1/mod_label/intro/a.pdf?time=1760000000000")
    for suffix in ("", "abc", "-1", "1&time=2", "1&action=delete", "9" * 17):
        with pytest.raises(FadError):
            validate_url(ORIGIN + "/pluginfile.php/1/a.pdf?time=" + suffix)
    for url, method in (
        (ORIGIN + "/mod/assign/view.php?id=17&action=editsubmission", "GET"),
        (ORIGIN + "/mod/assign/view.php?id=17", "POST"),
        (ORIGIN + "/course/view.php?id=1&time=123", "GET"),
    ):
        with pytest.raises(FadError):
            validate_url(url, method)


def test_redirect_rejected_before_following():
    client = HttpClient()
    response = Mock(status_code=307, headers={"Location": "https://evil.test/login"})
    client.session.request = Mock(return_value=response)
    with pytest.raises(FadError):
        client.request(ORIGIN + "/login/index.php", "POST", data={"password": "SENTINEL"})
    assert client.session.request.call_count == 1
    response.close.assert_called_once()
    client.close()


def test_blocks_private_dns(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(OSError, match="non pubblico"):
        PublicHTTPSConnection("fad.its-ictpiemonte.it")._new_conn()


def test_ajax_write_method_not_sent():
    client = HttpClient()
    client.session.request = Mock()
    with pytest.raises(FadError):
        client.request(
            ORIGIN + "/lib/ajax/service.php",
            "POST",
            json=[{"methodname": "mod_quiz_process_attempt"}],
        )
    client.session.request.assert_not_called()
    client.close()


def test_cancel_and_size_limit():
    client = HttpClient()
    client.cancel.set()
    with pytest.raises(FadError, match="annullata"):
        client.request(ORIGIN + "/my/")
    client.cancel.clear()
    response = Mock(fad_started=time.monotonic())
    response.iter_content.return_value = [b"123", b"456"]
    with pytest.raises(FadError, match="limite"):
        list(client.chunks(response, 5))
    client.close()


def test_cancel_interrupts_retry_after_without_another_request():
    client = HttpClient()
    retry_started = Event()
    response = Mock(status_code=429, headers={"Retry-After": "30"})
    response.close.side_effect = retry_started.set
    client.session.request = Mock(return_value=response)
    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            result = worker.submit(client.request, ORIGIN + "/my/")
            try:
                assert retry_started.wait(5), "Il worker non ha raggiunto il retry"
            finally:
                client.cancel.set()
            with pytest.raises(FadError) as error:
                result.result(timeout=5)
            assert error.value.code == "CANCELLED"
        client.session.request.assert_called_once()
    finally:
        client.cancel.set()
        client.close()


def test_stream_request_budget_prevents_publishing_another_chunk():
    client = HttpClient()
    response = Mock(fad_started=time.monotonic() - client.limits.request_seconds - 1)
    response.iter_content.return_value = [b"expired payload"]
    try:
        with pytest.raises(FadError) as error:
            next(client.chunks(response))
        assert error.value.code == "LIMIT"
    finally:
        client.close()


def test_moodle_login_session_redirect_is_followed_without_password():
    client = HttpClient()
    first = Mock(status_code=303, headers={"Location": ORIGIN + "/login/index.php?testsession=12"})
    second = Mock(status_code=303, headers={"Location": ORIGIN + "/my/index.php"})
    final = Mock(status_code=200, headers={})
    client.session.request = Mock(side_effect=[first, second, final])
    assert (
        client.request(ORIGIN + "/login/index.php", "POST", data={"password": "SENTINEL"}) is final
    )
    calls = client.session.request.call_args_list
    assert calls[1].args == ("GET", ORIGIN + "/login/index.php?testsession=12")
    assert all("data" not in call.kwargs for call in calls[1:])
    client.close()


@pytest.mark.parametrize(
    "query",
    [
        "testsession=abc",
        "testsession=-1",
        "testsession=0",
        "testsession=1&testsession=2",
        "testsession=1&delete=1",
    ],
)
def test_invalid_login_session_redirect_remains_blocked(query):
    with pytest.raises(FadError):
        validate_url(ORIGIN + "/login/index.php?" + query)

def test_retry_after_beyond_remaining_budget_is_deferred():
    from fad_downloader.domain import Limits

    client = HttpClient(limits=Limits(request_seconds=5))
    response = Mock(status_code=429, headers={"Retry-After": "30"})
    client.session.request = Mock(return_value=response)
    try:
        with pytest.raises(FadError) as error:
            client.request(ORIGIN + "/my/")
        assert error.value.code == "RATE_LIMITED"
        response.close.assert_called_once()
        client.session.request.assert_called_once()
        connect, read = client.session.request.call_args.kwargs["timeout"]
        assert 0 < connect == read <= 5
    finally:
        client.close()


def test_empty_transfer_checks_cancellation_at_end():
    client = HttpClient()
    response = Mock(fad_started=time.monotonic())

    def empty_stream(_):
        client.cancel.set()
        yield from ()

    response.iter_content.side_effect = empty_stream
    try:
        with pytest.raises(FadError) as error:
            list(client.chunks(response))
        assert error.value.code == "CANCELLED"
    finally:
        client.close()
