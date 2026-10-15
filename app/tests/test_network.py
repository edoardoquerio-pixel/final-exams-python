import time
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
