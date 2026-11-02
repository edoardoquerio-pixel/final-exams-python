"""Synthetic tests only: never authenticate or contact FAD during pytest."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location(
    "integrity_helper", Path(__file__).resolve().parents[1] / "verify_fad_integrity.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class Response:
    status_code = 200

    def __init__(self, chunks, headers=None):
        self.chunks = chunks
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield from self.chunks


def test_fresh_bytes_and_no_conditional_request():
    calls = []

    def request(url, **kwargs):
        calls.append(kwargs)
        return Response([b"a", b"bc"], {"Content-Length": "3"})

    budget = [0]
    assert audit.remote_digest(SimpleNamespace(request=request), "unused", budget) == (
        3, hashlib.sha256(b"abc").hexdigest()
    )
    assert budget == [3]
    assert calls == [{"headers": {"Cache-Control": "no-cache"}}]


def test_truncated_response_rejected():
    http = SimpleNamespace(request=lambda *a, **k: Response([b"abc"], {"Content-Length": "4"}))
    with pytest.raises(ValueError, match="truncated"):
        audit.remote_digest(http, "unused", [0])


def test_cached_304_rejected():
    response = Response([])
    response.status_code = 304
    http = SimpleNamespace(request=lambda *a, **k: response)
    with pytest.raises(ValueError, match="status"):
        audit.remote_digest(http, "unused", [0])


def test_local_bytes_and_escape(tmp_path):
    (tmp_path / "material").write_bytes(b"original")
    first = audit.local_digest(tmp_path, "material")
    (tmp_path / "material").write_bytes(b"modified")
    assert first != audit.local_digest(tmp_path, "material")
    with pytest.raises(ValueError, match="unsafe"):
        audit.local_digest(tmp_path, "../outside")


def test_visible_feedback_missing_is_reported():
    source = b'<div class="qtext">Question <b>one</b><span hidden>secret</span></div><div class="rightanswer">Correct answer</div>'
    assert audit.semantic_checks([source], b"<p>Question one Correct answer</p>") == (3, 0)
    assert audit.semantic_checks([source], b"<p>Question one</p>") == (3, 1)


def test_budget_exhausted(monkeypatch):
    monkeypatch.setattr(audit, "Limits", lambda: SimpleNamespace(file_bytes=10, run_bytes=2, request_seconds=300))
    http = SimpleNamespace(request=lambda *a, **k: Response([b"abc"]))
    with pytest.raises(ValueError, match="limit"):
        audit.remote_digest(http, "unused", [0])


def test_page_text_is_checked():
    source = b'<body id="page-mod-page-view"><main id="region-main"><div class="generalbox"><p>Lesson text</p></div></main></body>'
    assert audit.semantic_checks([source], b"<p>Lesson text</p>", page=True) == (1, 0)
    assert audit.semantic_checks([source], b"<p>Other text</p>", page=True) == (1, 1)


def test_selected_answer_counts_deduplicate_question_pages():
    source = b'<div class="que" id="q1"><input type="radio" checked><input type="radio"></div>'
    assert audit.answer_markers([source, source], b"[selezionata] [non selezionata]") == {
        "expected_selected": 1, "actual_selected": 1,
        "expected_unselected": 1, "actual_unselected": 1,
    }
