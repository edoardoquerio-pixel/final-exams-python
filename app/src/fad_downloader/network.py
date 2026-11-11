"""Client HTTPS limitato alle operazioni Moodle di lettura."""

import ipaddress
import re
import socket
import time
from threading import Event
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.util.connection import create_connection

from .domain import FadError, Limits, ORIGIN, check_cancel
from .observability import event, failure, monitored, query_names, route_name
import logging

READ_METHODS = {
    "core_course_get_enrolled_courses_by_timeline_classification",
    "core_course_get_contents",
    "core_get_fragment",
}


def validate_ajax_payload(payload):
    if not isinstance(payload, list) or not payload:
        raise FadError("URL", "Metodo AJAX non consentito.")
    for item in payload:
        if not isinstance(item, dict) or item.get("methodname") not in READ_METHODS:
            raise FadError("URL", "Metodo AJAX non consentito.")
        if item["methodname"] == "core_get_fragment":
            args = item.get("args", {})
            try:
                if (
                    set(args) != {"component", "callback", "contextid", "args"}
                    or args["component"] != "theme_snap"
                    or args["callback"] != "section"
                    or type(args["contextid"]) is not int
                    or args["contextid"] <= 0
                ):
                    raise ValueError
                values = args["args"]
                if (
                    not isinstance(values, list)
                    or len(values) != 2
                    or any(set(v) != {"name", "value"} for v in values)
                ):
                    raise ValueError
                params = {v["name"]: str(v["value"]) for v in values}
                if (
                    set(params) != {"courseid", "section"}
                    or any(not v.isascii() or not v.isdigit() for v in params.values())
                    or int(params["courseid"]) <= 0
                ):
                    raise ValueError
            except (TypeError, KeyError, ValueError):
                raise FadError(
                    "URL", "Solo i frammenti di lettura delle sezioni Snap sono consentiti."
                ) from None


ROUTES = {
    "/": set(),
    "/index.php": set(),
    "/my/": {"myoverviewpage"},
    "/my/index.php": {"myoverviewpage"},
    "/login/index.php": {"testsession"},
    "/login/logout.php": {"sesskey"},
    "/course/view.php": {"id", "section", "sectionid"},
    "/mod/resource/view.php": {"id", "redirect"},
    "/mod/folder/view.php": {"id"},
    "/mod/assign/view.php": {"id"},
    "/mod/page/view.php": {"id"},
    "/mod/book/view.php": {"id", "chapterid"},
    "/mod/book/tool/print/index.php": {"id", "chapterid"},
    "/mod/quiz/view.php": {"id"},
    "/mod/quiz/review.php": {"attempt", "cmid", "page", "showall"},
    "/lib/ajax/service.php": {"sesskey", "info"},
}


def validate_url(url: str, method: str = "GET", allow_logout=False) -> None:
    try:
        parts = urlsplit(url)
        origin = urlsplit(ORIGIN)
        if (
            parts.scheme != "https"
            or parts.hostname != origin.hostname
            or parts.port not in (None, 443)
            or parts.username
            or parts.password
        ):
            raise ValueError
        path = unquote(parts.path)
        if path == "/login/logout.php" and not allow_logout:
            raise ValueError
        if ".." in path.split("/") or "\\" in path or "%" in path or any(ord(c) < 32 for c in url):
            raise ValueError
        allowed = (
            {"forcedownload", "token", "time"} if path.startswith("/pluginfile.php/") else ROUTES.get(path)
        )
        if allowed is None or not set(parse_qs(parts.query, keep_blank_values=True)).issubset(allowed):
            raise ValueError
        if path == "/mod/assign/view.php":
            query = parse_qs(parts.query, keep_blank_values=True)
            ids = query.get("id", [])
            if len(ids) != 1 or not ids[0].isascii() or not ids[0].isdigit() or int(ids[0]) <= 0:
                raise ValueError
        if path.startswith("/pluginfile.php/"):
            query = parse_qs(parts.query, keep_blank_values=True)
            if "time" in query and (
                len(query["time"]) != 1
                or not query["time"][0].isascii()
                or not query["time"][0].isdigit()
                or len(query["time"][0]) > 16
            ):
                raise ValueError
        if path == "/login/index.php" and "testsession" in parse_qs(parts.query):
            values = parse_qs(parts.query)["testsession"]
            if (
                method != "GET"
                or len(values) != 1
                or not values[0].isascii()
                or not values[0].isdigit()
                or int(values[0]) <= 0
            ):
                raise ValueError
        if method not in {"GET", "POST"} or (
            method == "POST" and path not in {"/login/index.php", "/lib/ajax/service.php"}
        ):
            raise ValueError
    except ValueError:
        raise FadError("URL", "URL o azione non consentita dalla policy FAD.") from None


class PublicHTTPSConnection(HTTPSConnection):
    """Connette direttamente all'IP pubblico verificato; SNI resta il nome originale."""

    def _new_conn(self):
        records = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        for _, _, _, _, address in records:
            if not ipaddress.ip_address(address[0]).is_global:
                raise OSError("Indirizzo non pubblico")
        for _, _, _, _, address in records:
            try:
                return create_connection(
                    (address[0], self.port),
                    self.timeout,
                    source_address=self.source_address,
                    socket_options=self.socket_options,
                )
            except OSError:
                continue
        raise OSError("Connessione non disponibile")


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = PublicHTTPSConnection


class PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            **self.poolmanager.pool_classes_by_scheme,
            "https": PublicHTTPSPool,
        }


class HttpClient:
    def __init__(self, cancel: Event | None = None, limits=None):
        self.cancel = cancel or Event()
        self.limits = limits or Limits()
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount("https://", PublicAdapter(max_retries=0))
        self.session.headers.update(
            {"User-Agent": "FADDownloader/0.1.0", "Accept-Language": "it,en;q=0.5"}
        )
        self.last_request = 0.0

    def close(self):
        event("network.session_closed", level=logging.DEBUG)
        self.session.close()
        self.session.cookies.clear()

    @monitored("network.request")
    def request(self, url, method="GET", allow_logout=False, **kwargs):
        start = time.monotonic()
        deadline = start + self.limits.request_seconds
        redirects, retries = 0, 0

        def remaining():
            check_cancel(self.cancel)
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise FadError("LIMIT", "Tempo massimo della richiesta superato.")
            return budget

        def wait(delay):
            self.cancel.wait(min(delay, remaining()))
            remaining()
        if method == "POST" and urlsplit(url).path == "/lib/ajax/service.php":
            payload = kwargs.get("json", [])
            validate_ajax_payload(payload)
        while True:
            event(
                "network.send",
                level=logging.DEBUG,
                method=method,
                route=route_name(url),
                query_keys=query_names(url),
                attempt=retries + 1,
                redirects=redirects,
            )
            check_cancel(self.cancel)
            validate_url(url, method, allow_logout)
            wait(max(0, 0.25 - (time.monotonic() - self.last_request)))
            timeout = min(self.limits.timeout, remaining())
            try:
                self.last_request = time.monotonic()
                response = self.session.request(
                    method,
                    url,
                    allow_redirects=False,
                    stream=True,
                    timeout=(timeout, timeout),
                    **kwargs,
                )
            except requests.RequestException as exc:
                failure("network.connection_failed", exc)
                remaining()
                if method == "GET" and retries < 2:
                    retries += 1
                    wait(retries)
                    continue
                raise FadError(
                    "NETWORK", "Connessione fallita. Controllare rete e certificato HTTPS."
                ) from None
            try:
                remaining()
            except FadError:
                response.close()
                raise
            event(
                "network.response",
                level=logging.DEBUG,
                method=method,
                route=route_name(url),
                http_status=response.status_code,
                elapsed_ms=round((time.monotonic() - start) * 1000),
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                target = urljoin(url, response.headers.get("Location", ""))
                event(
                    "network.redirect",
                    level=logging.DEBUG,
                    route=route_name(target),
                    http_status=response.status_code,
                )
                response.close()
                redirects += 1
                if redirects > 5:
                    raise FadError("NETWORK", "Troppi reindirizzamenti.")
                validate_url(target, method if response.status_code in {307, 308} else "GET")
                if response.status_code in {301, 302, 303}:
                    method, kwargs = "GET", {}
                url = target
                continue
            if (
                response.status_code in {429, 500, 502, 503, 504}
                and method == "GET"
                and retries < 2
            ):
                delay = response.headers.get("Retry-After", str(2**retries))
                response.close()
                seconds = delay.strip()
                if not re.fullmatch(r"0*[0-9]{1,2}", seconds):
                    raise FadError("RATE_LIMITED", "Server occupato: riprovare più tardi.")
                delay_seconds = int(seconds.lstrip("0") or "0")
                if delay_seconds > 30 or delay_seconds >= remaining():
                    raise FadError("RATE_LIMITED", "Server occupato: riprovare più tardi.")
                retries += 1
                event("network.retry", attempt=retries + 1, http_status=response.status_code)
                wait(delay_seconds)
                continue
            if response.status_code >= 400:
                code = (
                    "AUTH_REQUIRED"
                    if response.status_code == 401
                    else "ACCESS_DENIED"
                    if response.status_code == 403
                    else "NETWORK"
                )
                status = response.status_code
                response.close()
                raise FadError(code, f"Risorsa non disponibile (HTTP {status}).")
            response.fad_started = start
            return response

    def chunks(self, response, limit=None):
        limit = self.limits.file_bytes if limit is None else limit
        size = 0
        def check_transfer():
            check_cancel(self.cancel)
            if time.monotonic() - response.fad_started >= self.limits.request_seconds:
                raise FadError("LIMIT", "Tempo massimo del trasferimento superato.")

        try:
            check_transfer()
            for chunk in response.iter_content(64 * 1024):
                check_transfer()
                size += len(chunk)
                if size > limit:
                    raise FadError("LIMIT", "Risposta oltre il limite consentito.")
                if chunk:
                    yield chunk
            check_transfer()
        except requests.RequestException:
            check_transfer()
            raise FadError("NETWORK", "Trasferimento interrotto.") from None
        finally:
            event("network.stream_finished", level=logging.DEBUG, bytes=size)

    def document(self, url, method="GET", **kwargs):
        with self.request(url, method, **kwargs) as response:
            content = b"".join(self.chunks(response, self.limits.document_bytes))
            return content, response.url
