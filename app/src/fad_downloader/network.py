"""Client HTTPS limitato alle operazioni Moodle di lettura."""

import ipaddress
import socket
import time
from threading import Event
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.util.connection import create_connection

from .domain import FadError, ORIGIN, check_cancel

READ_METHODS = {
    "core_course_get_enrolled_courses_by_timeline_classification",
    "core_course_get_contents",
}
ROUTES = {
    "/": set(),
    "/my/": {"myoverviewpage"},
    "/login/index.php": set(),
    "/course/view.php": {"id", "section", "sectionid"},
    "/mod/resource/view.php": {"id", "redirect"},
    "/mod/folder/view.php": {"id"},
    "/mod/page/view.php": {"id"},
    "/mod/book/view.php": {"id", "chapterid"},
    "/mod/book/tool/print/index.php": {"id", "chapterid"},
    "/mod/quiz/view.php": {"id"},
    "/mod/quiz/review.php": {"attempt", "cmid", "page", "showall"},
    "/lib/ajax/service.php": {"sesskey", "info"},
}


def validate_url(url: str, method: str = "GET") -> None:
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
        if ".." in path.split("/") or "\\" in path or "%" in path or any(ord(c) < 32 for c in url):
            raise ValueError
        allowed = (
            {"forcedownload", "token"} if path.startswith("/pluginfile.php/") else ROUTES.get(path)
        )
        if allowed is None or not set(parse_qs(parts.query)).issubset(allowed):
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
    def __init__(self, cancel: Event | None = None):
        self.cancel = cancel or Event()
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount("https://", PublicAdapter(max_retries=0))
        self.session.headers.update(
            {"User-Agent": "FADDownloader/0.0.1", "Accept-Language": "it,en;q=0.5"}
        )
        self.last_request = 0.0

    def close(self):
        self.session.close()
        self.session.cookies.clear()

    def request(self, url, method="GET", **kwargs):
        start = time.monotonic()
        redirects, retries = 0, 0
        if method == "POST" and urlsplit(url).path == "/lib/ajax/service.php":
            payload = kwargs.get("json", [])
            if not payload or any(item.get("methodname") not in READ_METHODS for item in payload):
                raise FadError("URL", "Metodo AJAX non consentito.")
        while True:
            check_cancel(self.cancel)
            validate_url(url, method)
            self.cancel.wait(max(0, 0.25 - (time.monotonic() - self.last_request)))
            check_cancel(self.cancel)
            try:
                self.last_request = time.monotonic()
                response = self.session.request(
                    method, url, allow_redirects=False, stream=True, timeout=(10, 10), **kwargs
                )
            except requests.RequestException:
                if method == "GET" and retries < 2:
                    retries += 1
                    self.cancel.wait(retries)
                    continue
                raise FadError(
                    "NETWORK", "Connessione fallita. Controllare rete e certificato HTTPS."
                ) from None
            if time.monotonic() - start > 300:
                response.close()
                raise FadError("LIMIT", "Tempo massimo della richiesta superato.")
            if response.status_code in {301, 302, 303, 307, 308}:
                target = urljoin(url, response.headers.get("Location", ""))
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
                if not delay.isdigit() or int(delay) > 30:
                    raise FadError("RATE_LIMITED", "Server occupato: riprovare più tardi.")
                retries += 1
                self.cancel.wait(int(delay))
                continue
            if response.status_code >= 400:
                code = "ACCESS_DENIED" if response.status_code in {401, 403} else "NETWORK"
                status = response.status_code
                response.close()
                raise FadError(code, f"Risorsa non disponibile (HTTP {status}).")
            response.fad_started = start
            return response

    def chunks(self, response, limit=2 * 1024**3):
        size = 0
        try:
            for chunk in response.iter_content(64 * 1024):
                check_cancel(self.cancel)
                if time.monotonic() - response.fad_started > 300:
                    raise FadError("LIMIT", "Tempo massimo del trasferimento superato.")
                size += len(chunk)
                if size > limit:
                    raise FadError("LIMIT", "Risposta oltre il limite consentito.")
                if chunk:
                    yield chunk
        except requests.RequestException:
            raise FadError("NETWORK", "Trasferimento interrotto.") from None

    def document(self, url, method="GET", **kwargs):
        with self.request(url, method, **kwargs) as response:
            content = b"".join(self.chunks(response, 20 * 1024**2))
            return content, response.url
