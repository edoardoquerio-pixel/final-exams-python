"""Contratti condivisi tra interfaccia, adapter Moodle e servizi."""

from dataclasses import dataclass, field
from threading import Event
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import hashlib

ORIGIN = "https://fad.its-ictpiemonte.it"


class FadError(Exception):
    """Errore pubblico: messaggio controllato, mai URL o eccezioni con segreti."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise FadError("CANCELLED", "Operazione annullata.")


def stable_url(url: str) -> str:
    parts = urlsplit(url)
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query)
        if k.casefold() not in {"token", "sesskey", "forcedownload"}
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def identifier(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Account:
    origin: str
    user_id: str

    @property
    def key(self) -> str:
        return identifier(f"{self.origin}:{self.user_id}")


@dataclass(frozen=True)
class Course:
    id: int
    name: str
    url: str


@dataclass(frozen=True)
class Resource:
    id: str
    course_id: int
    course: str
    section: str
    activity_id: int
    name: str
    kind: str
    url: str = field(repr=False)
    size: int | None = None


@dataclass
class Catalog:
    courses: list[Course] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Task:
    resource: Resource
    relative: str


@dataclass
class Result:
    resource_id: str
    name: str
    status: str
    path: str = ""
    message: str = ""


@dataclass(frozen=True)
class Naming:
    course: str = "{course_id}_{course_name}"
    section: str = "{section_name}"
    materials: str = "Materiali"
    quizzes: str = "Test"
