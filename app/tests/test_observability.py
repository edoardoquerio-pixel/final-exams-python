import json
import logging
import os
import stat

import pytest

from fad_downloader.cli import main
from fad_downloader.domain import FadError
from fad_downloader.observability import configure, event, failure, logger, route_name, span


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_log_rejects_secrets_payloads_and_unstructured_messages(tmp_path):
    path = configure("DEBUG", tmp_path)
    event(
        "safe.test",
        password="PASSWORD_SENTINEL",
        username="USER_SENTINEL",
        cookie="COOKIE_SENTINEL",
        url="https://example.test/?token=TOKEN_SENTINEL",
        route=route_name(
            "https://example.test/pluginfile.php/PRIVATE_TITLE.pdf?token=TOKEN_SENTINEL"
        ),
    )
    logger.error("PASSWORD_SENTINEL")
    try:
        raise RuntimeError("PASSWORD_SENTINEL TOKEN_SENTINEL")
    except RuntimeError as exc:
        failure("safe.error", exc)
    text = path.read_text(encoding="utf-8")
    assert all(
        secret not in text
        for secret in (
            "PASSWORD_SENTINEL",
            "USER_SENTINEL",
            "COOKIE_SENTINEL",
            "TOKEN_SENTINEL",
            "PRIVATE_TITLE",
        )
    )
    events = read_events(path)
    assert events[-1]["error_type"] == "RuntimeError"
    assert events[-1]["frames"]


def test_span_correlation_and_error_code(tmp_path):
    path = configure("DEBUG", tmp_path)
    with pytest.raises(FadError):
        with span("outer"):
            with span("inner"):
                raise FadError("AUTH_REQUIRED", "PRIVATE_MESSAGE")
    events = [e for e in read_events(path) if e["event"].startswith(("outer", "inner"))]
    assert len({e["operation"] for e in events}) == 1
    assert events[-1]["code"] == "AUTH_REQUIRED"
    assert "PRIVATE_MESSAGE" not in path.read_text()


def test_rotation_and_private_permissions(tmp_path):
    path = configure("DEBUG", tmp_path, max_bytes=600, backups=2)
    for _ in range(40):
        event("rotation.test", count=42)
    assert path.exists()
    assert len(list(tmp_path.glob("*.jsonl.*"))) == 2
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert all(read_events(p) for p in tmp_path.iterdir())


def test_disabled_logging_does_not_create_directory(tmp_path):
    path = tmp_path / "logs"
    assert configure(directory=path, enabled=False) is None
    event("discarded.event")
    assert not path.exists()


def test_cli_logging_covers_download_and_verify(tmp_path, capsys):
    workspace, logs = tmp_path / "workspace", tmp_path / "logs"
    assert (
        main(
            [
                "--log-level",
                "DEBUG",
                "--log-dir",
                str(logs),
                "download",
                "--demo",
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    capsys.readouterr()
    path = next(logs.glob("*.jsonl"))
    events = read_events(path)
    names = {e["event"] for e in events}
    assert {
        "app.start",
        "plan.result",
        "download.task_start",
        "download.task_result",
        "download.result",
        "storage.atomic_write",
        "storage.lock_acquired",
        "app.exit",
    } <= names
    assert main(["--log-dir", str(logs), "verify", "--workspace", str(workspace)]) == 0
    assert "integrity.result" in {e["event"] for e in read_events(path)}


def test_debug_filter_and_logger_configuration_is_idempotent(tmp_path):
    path = configure("INFO", tmp_path)
    configure("INFO", tmp_path)
    event("single.event")
    event("debug.event", level=logging.DEBUG)
    names = [e["event"] for e in read_events(path)]
    assert names.count("single.event") == 1
    assert "debug.event" not in names
