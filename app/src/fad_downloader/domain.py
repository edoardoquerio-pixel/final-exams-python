"""Contratti condivisi tra interfaccia, adapter Moodle e servizi."""

from dataclasses import dataclass, field
from threading import Event
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import hashlib

ORIGIN = "https://fad.its-ictpiemonte.it"
SUPPORTED_RESOURCE_KINDS = {"file", "page", "book", "quiz_review"}


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
class Section:
    id: str
    course_id: int
    name: str
    index: int
    available: bool = True


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
    subfolder: str = ""
    section_index: int = 0
    activity_name: str = ""
    attempt_id: str = ""
    section_id: str = ""


@dataclass
class Catalog:
    courses: list[Course] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)


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
    activity: str = "{activity_id}_{activity_name}"


@dataclass(frozen=True)
class Limits:
    document_bytes: int = 20 * 1024**2
    file_bytes: int = 2 * 1024**3
    run_bytes: int = 10 * 1024**3
    pages: int = 10000
    timeout: int = 10
    request_seconds: int = 300

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if type(value) is not int or value <= 0:
                raise FadError("CONFIG", f"Limite {name} non valido.")
        if (
            self.document_bytes > 100 * 1024**2
            or self.file_bytes > 20 * 1024**3
            or self.run_bytes > 100 * 1024**3
            or self.pages > 100000
            or self.timeout > 60
            or self.request_seconds > 3600
        ):
            raise FadError("CONFIG", "Limiti oltre il massimo consentito.")
