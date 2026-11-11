"""Workspace privato, lock di processo e scritture atomiche.

Su Linux le aperture sono relative a directory descriptor con O_NOFOLLOW.
Su Windows il percorso viene validato: il collaudo di sicurezza principale è Linux.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from string import Formatter
import uuid

from .domain import Account, FadError


def clean_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", value).strip().rstrip(" .") or "Senza_nome"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", value, re.I):
        value = "_" + value
    if len(value.encode("utf-8")) > 160:
        suffix = hashlib.sha256(value.encode()).hexdigest()[:10]
        value = value.encode()[:140].decode("utf-8", "ignore") + "_" + suffix
    return value


def render_name(template: str, values: dict) -> str:
    if len(template) > 200:
        raise FadError("CONFIG", "Template troppo lungo.")
    try:
        for _, key, spec, conversion in Formatter().parse(template):
            if key is not None and (key not in values or spec or conversion):
                raise ValueError
        name = template.format_map(values)
    except (ValueError, KeyError, IndexError):
        raise FadError("CONFIG", "Segnaposto non valido nel template.") from None
    if not name.strip() or name in {".", ".."} or "/" in name or "\\" in name:
        raise FadError("CONFIG", "Il template deve produrre un solo nome di cartella.")
    return clean_name(name)


def components(relative: str) -> list[str]:
    if not isinstance(relative, str) or len(relative) > 2000:
        raise FadError("PATH", "Percorso non valido.")
    parts = relative.split("/")
    if any(not p or p in {".", ".."} or clean_name(p) != p for p in parts):
        raise FadError("PATH", "Percorso non sicuro.")
    return parts


class SafeRoot:
    def __init__(self, root: Path, create: bool = False):
        self.root = Path(os.path.abspath(root.expanduser()))
        for parent in [*reversed(self.root.parents), self.root]:
            if parent.is_symlink():
                raise FadError("PATH", "La directory non può attraversare link simbolici.")
        if create:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise FadError("PATH", "Directory di lavoro non trovata.")

    @contextmanager
    def parent(self, relative: str, create: bool = False):
        parts = components(relative)
        if os.name == "posix":
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for name in parts[:-1]:
                    if create:
                        try:
                            os.mkdir(name, 0o700, dir_fd=fd)
                        except FileExistsError:
                            pass
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = child
                yield fd, parts[-1]
            finally:
                os.close(fd)
        else:
            path = self.root
            for name in parts[:-1]:
                path /= name
                if path.is_symlink():
                    raise FadError("PATH", "Link simbolico non consentito.")
                if create:
                    path.mkdir(mode=0o700, exist_ok=True)
            target = path / parts[-1]
            if target.is_symlink():
                raise FadError("PATH", "Link simbolico non consentito.")
            yield None, str(target)

    @contextmanager
    def open_read(self, relative: str):
        with self.parent(relative) as (fd, name):
            handle = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=fd)
            if not stat.S_ISREG(os.fstat(handle).st_mode):
                os.close(handle)
                raise FadError("PATH", "Non è un file regolare.")
            with os.fdopen(handle, "rb") as stream:
                yield stream

    def read(self, relative: str, limit: int = 20 * 1024 * 1024) -> bytes:
        with self.open_read(relative) as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise FadError("LIMIT", "File di stato troppo grande.")
        return data

    def fingerprint(self, relative: str) -> tuple[int, str] | None:
        try:
            with self.open_read(relative) as handle:
                digest = hashlib.sha256()
                size = 0
                chunk = handle.read(256 * 1024)
                while chunk:
                    digest.update(chunk)
                    size += len(chunk)
                    chunk = handle.read(256 * 1024)
                return size, digest.hexdigest()
        except FileNotFoundError:
            return None

    def write(self, relative: str, chunks, expected="any") -> tuple[int, str]:
        """Il temporaneo non diventa definitivo prima di aver consumato/verificato i chunk."""
        with self.parent(relative, create=True) as (fd, name):
            temp = ".part-" + uuid.uuid4().hex
            if fd is None:
                temp = str(Path(name).with_name(temp))
            handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            try:
                size, digest = 0, hashlib.sha256()
                with os.fdopen(handle, "wb") as stream:
                    for chunk in chunks:
                        stream.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                if expected != "any" and self.fingerprint(relative) != expected:
                    raise FadError(
                        "CONFLICT", "File cambiato durante il trasferimento; copia preservata."
                    )
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise FadError("PATH", "Destinazione non regolare.")
                except FileNotFoundError:
                    pass
                os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
                if fd is not None:
                    os.fsync(fd)
                from .observability import event
                import logging

                event("storage.atomic_write", level=logging.DEBUG, bytes=size)
                return size, digest.hexdigest()
            finally:
                try:
                    os.unlink(temp, dir_fd=fd)
                except FileNotFoundError:
                    pass

    def json(self, relative: str, default=None):
        try:
            return json.loads(self.read(relative))
        except FileNotFoundError:
            return default
        except (ValueError, UnicodeError):
            raise FadError(
                "STATE", "File JSON corrotto; conservare una copia prima del recupero."
            ) from None

    def write_json(self, relative: str, data):
        return self.write(relative, [json.dumps(data, ensure_ascii=False, indent=2).encode()])

    @contextmanager
    def lock(self):
        with self.parent(".fad/workspace.lock", create=True) as (fd, name):
            handle = os.open(
                name, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=fd
            )
            locked = False
            try:
                if os.name == "posix":
                    import fcntl

                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise FadError(
                            "LOCK", "Workspace già utilizzato da un'altra esecuzione."
                        ) from None
                else:
                    import msvcrt

                    if os.fstat(handle).st_size == 0:
                        os.write(handle, b"0")
                    os.lseek(handle, 0, 0)
                    try:
                        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
                    except OSError:
                        raise FadError("LOCK", "Workspace già utilizzato.") from None
                locked = True
                from .observability import event
                import logging

                event("storage.lock_acquired", level=logging.DEBUG)
                yield
            finally:
                if locked:
                    event("storage.lock_released", level=logging.DEBUG)
                if locked and os.name != "posix":
                    os.lseek(handle, 0, 0)
                    msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
                os.close(handle)


def load_manifest(root: SafeRoot, account: Account | None = None):
    data = root.json(
        ".fad/manifest.json",
        {"version": 1, "account": account.key if account else "", "records": {}},
    )
    try:
        if data["version"] != 1 or not isinstance(data["records"], dict):
            raise ValueError
        if not isinstance(data.get("account"), str):
            raise ValueError
        if account and data["account"] != account.key:
            raise FadError("ACCOUNT", "Questo workspace appartiene a un altro account.")
        for key, record in data["records"].items():
            if not re.fullmatch(r"[0-9a-f]{64}", key):
                raise ValueError
            components(record["path"])
            if any(
                not isinstance(record.get(field, ""), str) for field in ("name", "course", "kind")
            ):
                raise ValueError
            if "base" in record:
                components(record["base"])
            if not isinstance(record.get("assets", []), list):
                raise ValueError
            for item in [record, *record.get("assets", [])]:
                components(item["path"])
                if (
                    not isinstance(item["size"], int)
                    or item["size"] < 0
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                ):
                    raise ValueError
    except (KeyError, TypeError, ValueError):
        raise FadError("STATE", "Schema del manifest non valido o non supportato.") from None
    return data
