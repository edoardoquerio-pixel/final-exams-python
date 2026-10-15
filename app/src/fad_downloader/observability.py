"""Eventi strutturati senza dati autenticati, payload HTTP o messaggi remoti."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json
import logging
import os
import re
import time
import traceback
import uuid

from .domain import FadError
from .storage import SafeRoot

logger = logging.getLogger("fad_downloader.events")
logger.addHandler(logging.NullHandler())
logger.propagate = False
operation = ContextVar("fad_operation", default="")
session_id = uuid.uuid4().hex[:12]
log_path = None
FIELDS = {
    "operation",
    "code",
    "error_type",
    "resource_id",
    "kind",
    "status",
    "method",
    "route",
    "http_status",
    "attempt",
    "redirects",
    "bytes",
    "resources",
    "courses",
    "sections",
    "warnings",
    "issues",
    "files",
    "partial",
    "elapsed_ms",
    "demo",
    "command",
    "backend",
    "stored",
    "frames",
    "count",
    "query_keys",
}
ROUTES = {
    "/",
    "/index.php",
    "/my/",
    "/my/index.php",
    "/login/index.php",
    "/login/logout.php",
    "/course/view.php",
    "/lib/ajax/service.php",
    "/mod/resource/view.php",
    "/mod/folder/view.php",
    "/mod/page/view.php",
    "/mod/book/view.php",
    "/mod/book/tool/print/index.php",
    "/mod/quiz/view.php",
    "/mod/quiz/review.php",
}


def route_name(url):
    from urllib.parse import urlsplit

    try:
        path = urlsplit(url).path
        return (
            "pluginfile"
            if path.startswith("/pluginfile.php/")
            else path
            if path in ROUTES
            else "blocked"
        )
    except ValueError:
        return "invalid"


def query_names(url):
    from urllib.parse import parse_qs, urlsplit

    allowed = {
        "testsession",
        "sesskey",
        "token",
        "forcedownload",
        "id",
        "attempt",
        "page",
        "showall",
        "cmid",
        "section",
        "sectionid",
        "chapterid",
        "myoverviewpage",
        "info",
        "redirect",
    }
    try:
        return ":".join(sorted(set(parse_qs(urlsplit(url).query)) & allowed))
    except ValueError:
        return "invalid"


def event(name, level=logging.INFO, **fields):
    """Schema chiuso: stringhe libere, URL, percorsi e segreti non sono ammessi."""
    if not re.fullmatch(r"[a-z0-9_.]+", name):
        name = "invalid_event"
    data = {"event": name, "session": session_id, "operation": operation.get()}
    for key, value in fields.items():
        if key not in FIELDS:
            continue
        if isinstance(value, (int, float, bool)):
            data[key] = value
        elif isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./:-]{0,120}", value):
            data[key] = value
    logger.log(level, "", extra={"event_data": data})


def failure(name, exc):
    # Solo nomi funzione e numeri di riga: niente testo dell'eccezione, sorgente o locals.
    frames = ":".join(
        f"{re.sub('[^A-Za-z0-9_]', '_', frame.name)}.{frame.lineno}"
        for frame in traceback.extract_tb(exc.__traceback__)[-4:]
    )
    event(
        name,
        logging.WARNING if isinstance(exc, FadError) else logging.ERROR,
        code=exc.code if isinstance(exc, FadError) else "UNEXPECTED",
        error_type=type(exc).__name__,
        frames=frames,
    )


@contextmanager
def span(name):
    parent = operation.get()
    token = operation.set(parent or uuid.uuid4().hex[:12])
    started = time.monotonic()
    event(name + ".start", level=logging.DEBUG)
    try:
        yield
    except Exception as exc:
        failure(name + ".failed", exc)
        raise
    else:
        event(name + ".done", elapsed_ms=round((time.monotonic() - started) * 1000))
    finally:
        operation.reset(token)


def monitored(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)

        return wrapped

    return decorate


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = dict(getattr(record, "event_data", {"event": "unstructured_record_suppressed"}))
        data.update(
            time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            level=record.levelname,
            thread=record.threadName,
            pid=os.getpid(),
        )
        return json.dumps(data, ensure_ascii=False)


class PrivateRotatingHandler(RotatingFileHandler):
    def _open(self):
        fd = os.open(
            self.baseFilename,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        return os.fdopen(fd, "a", encoding="utf-8")


def default_log_dir():
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base / "fad-downloader/logs"
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "fad-downloader/logs"
    )


def configure(level="INFO", directory=None, enabled=True, max_bytes=5 * 1024**2, backups=5):
    global log_path
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(logging.NullHandler())
    log_path = None
    if not enabled:
        return None
    try:
        root = SafeRoot(Path(directory) if directory else default_log_dir(), create=True)
        path = root.root / f"fad-downloader-{os.getpid()}.jsonl"
        if path.is_symlink():
            raise OSError
        handler = PrivateRotatingHandler(
            path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
        )
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level))
        log_path = path
        event("logging.ready")
        return path
    except (OSError, FadError):
        raise FadError(
            "LOGGING",
            "Impossibile aprire i log: controllare percorso e permessi oppure usare --no-log.",
        ) from None
