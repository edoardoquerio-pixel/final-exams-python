"""Catalogo sintetico offline: nessuna connessione o credenziale reale."""

import time
from threading import Event

from .domain import Account, Catalog, Course, ORIGIN, Resource, identifier

DATA = b"Esercizio dimostrativo FAD Downloader\nprint('Ciao Python')\n"
HTML = b'<html><div class="resourcecontent"><h2>Lezione demo</h2><p>Materiale sintetico offline.</p></div></html>'
QUIZ = b'<html><div class="que multichoice"><h2>Quanto fa 2 + 2?</h2><input type="radio" checked><label>4</label><input type="hidden" value="NON_ESPORTARE"><p>Esito: corretto</p></div></html>'


def catalog():
    course = Course(1, "Python - corso dimostrativo", ORIGIN + "/course/view.php?id=1")
    resources = []
    for name, kind, url, size in [
        ("esercizio.py", "file", ORIGIN + "/pluginfile.php/1/demo/esercizio.py", len(DATA)),
        ("Lezione introduttiva", "page", ORIGIN + "/mod/page/view.php?id=2", None),
        ("Quiz - tentativo 1", "quiz_review", ORIGIN + "/mod/quiz/review.php?attempt=1", None),
    ]:
        resources.append(
            Resource(
                identifier(url),
                1,
                course.name,
                "Introduzione",
                len(resources) + 1,
                name,
                kind,
                url,
                size,
            )
        )
    return Catalog([course], resources)


class DemoResponse:
    status_code = 200

    def __init__(self, url):
        self.url = url
        self.headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(DATA)),
        }
        self.fad_started = time.monotonic()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class DemoHttp:
    def __init__(self, cancel=None):
        self.cancel = cancel or Event()

    def request(self, url, **kwargs):
        return DemoResponse(url)

    def chunks(self, response, limit=None):
        yield DATA

    def document(self, url, **kwargs):
        return (QUIZ if "review.php" in url else HTML), url

    def close(self):
        pass


DEMO_ACCOUNT = Account(ORIGIN, "demo-offline")
