"""Pianificazione deterministica, download e report condivisi da GUI e CLI."""

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit
import uuid

from .domain import Account, FadError, Naming, Result, Task, check_cancel
from .exporter import export_bundle, html_page
from .storage import SafeRoot, clean_name, components, load_manifest, render_name

SUPPORTED = {"file", "page", "book", "quiz_review"}


def plan(resources, workspace: Path, account: Account, naming: Naming, mapping=None):
    mapping = mapping or {}
    records = {}
    if workspace.exists():
        records = load_manifest(SafeRoot(workspace), account)["records"]
    tasks = []
    for resource in resources:
        values = {
            "course_id": resource.course_id,
            "course_name": clean_name(resource.course),
            "section_name": clean_name(resource.section),
            "activity_id": resource.activity_id,
        }
        course = mapping.get(str(resource.course_id)) or render_name(naming.course, values)
        components(course)
        section = render_name(naming.section, values)
        category = naming.quizzes if resource.kind == "quiz_review" else naming.materials
        if clean_name(category) != category or not category:
            raise FadError("CONFIG", "Nome della cartella materiali/test non valido.")
        stem = clean_name(resource.name)
        if resource.kind == "file":
            url_name = clean_name(unquote(urlsplit(resource.url).path.rsplit("/", 1)[-1]))
            if not PurePosixPath(stem).suffix and PurePosixPath(url_name).suffix not in {
                "",
                ".php",
            }:
                stem += PurePosixPath(url_name).suffix
            name = f"{PurePosixPath(stem).stem}_{resource.id[:12]}{PurePosixPath(stem).suffix}"
        else:
            name = f"{stem}_{resource.id[:12]}"
        relative = f"{course}/{section}/{category}/{resource.activity_id}/{name}"
        record = records.get(resource.id)
        if record:
            relative = record.get("base", record["path"])
        components(relative)
        tasks.append(Task(resource, relative))
    return tasks


def save_settings(workspace, account, naming, mapping):
    root = SafeRoot(workspace, create=True)
    with root.lock():
        manifest = load_manifest(root, account)
        for folder in mapping.values():
            components(folder)
        root.write_json(".fad/manifest.json", manifest)
        root.write_json(
            ".fad/settings.json", {"version": 1, "naming": asdict(naming), "mapping": mapping}
        )


def load_settings(workspace):
    if not workspace.is_dir():
        return Naming(), {}
    data = SafeRoot(workspace).json(".fad/settings.json")
    if data is None:
        return Naming(), {}
    try:
        if data["version"] != 1 or not isinstance(data["mapping"], dict):
            raise ValueError
        naming = Naming(**data["naming"])
        if any(not isinstance(value, str) for value in asdict(naming).values()):
            raise ValueError
        for value in data["mapping"].values():
            components(value)
        return naming, data["mapping"]
    except (KeyError, ValueError, TypeError):
        raise FadError("CONFIG", "Configurazione workspace non valida.") from None


class Downloader:
    def __init__(self, http, account):
        self.http, self.account = http, account
        self.total_bytes = 0

    def transfer(self, root, url, relative, old=None, expected_size=None):
        before = root.fingerprint(relative)
        if before and (not old or before != (old["size"], old["sha256"])):
            raise FadError("CONFLICT", "File locale modificato o estraneo: conservato.")
        headers = {}
        if before and old:
            if old.get("etag"):
                headers["If-None-Match"] = old["etag"]
            elif old.get("modified"):
                headers["If-Modified-Since"] = old["modified"]
        with self.http.request(url, headers=headers) as response:
            if response.status_code == 304:
                if before is None:
                    raise FadError("INVALID_CONTENT", "HTTP 304 senza copia valida.")
                return dict(old), "invariato"
            if "/login/" in urlsplit(response.url).path:
                raise FadError("AUTH_REQUIRED", "Sessione scaduta: accedere e ritentare.")

            def chunks():
                size = 0
                first = True
                for chunk in self.http.chunks(response):
                    if first:
                        sample = chunk.lstrip().lower()
                        if "html" in response.headers.get(
                            "Content-Type", ""
                        ).lower() or sample.startswith((b"<!doctype html", b"<html")):
                            raise FadError(
                                "INVALID_CONTENT",
                                "HTML inatteso: usare l'esportazione pagina, non il download file.",
                            )
                        first = False
                    size += len(chunk)
                    self.total_bytes += len(chunk)
                    if self.total_bytes > 10 * 1024**3:
                        raise FadError("LIMIT", "Limite totale di 10 GiB raggiunto.")
                    yield chunk
                if expected_size is not None and size != expected_size:
                    raise FadError(
                        "INVALID_CONTENT", "Dimensione diversa da quella dichiarata da Moodle."
                    )
                length = response.headers.get("Content-Length")
                if (
                    length
                    and not response.headers.get("Content-Encoding")
                    and (not length.isdigit() or size != int(length))
                ):
                    raise FadError("INVALID_CONTENT", "Trasferimento incompleto.")

            size, digest = root.write(relative, chunks(), expected=before)
            record = {
                "path": relative,
                "size": size,
                "sha256": digest,
                "etag": response.headers.get("ETag"),
                "modified": response.headers.get("Last-Modified"),
            }
            status = (
                "invariato" if before == (size, digest) else "aggiornato" if old else "scaricato"
            )
            return record, status

    def export(self, root, task, old):
        if old:
            for item in [old, *old.get("assets", [])]:
                existing = root.fingerprint(item["path"])
                if existing is not None and existing != (item["size"], item["sha256"]):
                    raise FadError("CONFLICT", "Esportazione locale modificata: copia conservata.")
        generation = task.relative + "/" + uuid.uuid4().hex
        assets, names = [], set()

        def write_asset(url, name):
            if name not in names:
                record, _ = self.transfer(root, url, generation + "/assets/" + name)
                assets.append(record)
                names.add(name)
            return name

        content = export_bundle(self.http, task.resource, write_asset)
        relative = generation + "/index.html"
        size, digest = root.write(relative, [content], expected=None)
        return {
            "path": relative,
            "base": task.relative,
            "size": size,
            "sha256": digest,
            "assets": assets,
        }, "aggiornato" if old else "scaricato"

    def run(self, tasks, workspace, emit=lambda text: None):
        root = SafeRoot(workspace, create=True)
        results = []
        self.total_bytes = 0
        with root.lock():
            manifest = load_manifest(root, self.account)
            # Vincola il workspace anche se la prima operazione fallisce.
            root.write_json(".fad/manifest.json", manifest)
            auth_failed = False
            for task in tasks:
                r = task.resource
                emit("Download: " + r.name)
                try:
                    check_cancel(self.http.cancel)
                    if auth_failed:
                        raise FadError("AUTH_REQUIRED", "Da ritentare dopo un nuovo login.")
                    if r.kind not in SUPPORTED:
                        raise FadError("UNSUPPORTED", "Tipo attività non supportato nella 0.0.1.")
                    old = manifest["records"].get(r.id)
                    if r.kind == "file":
                        record, status = self.transfer(root, r.url, task.relative, old, r.size)
                    else:
                        record, status = self.export(root, task, old)
                    record.update(
                        {
                            "name": r.name,
                            "course": r.course,
                            "kind": r.kind,
                            "updated": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    manifest["records"][r.id] = record
                    root.write_json(".fad/manifest.json", manifest)
                    results.append(Result(r.id, r.name, status, record["path"]))
                except FadError as exc:
                    auth_failed |= exc.code == "AUTH_REQUIRED"
                    status = {
                        "CANCELLED": "annullato",
                        "CONFLICT": "conflitto",
                        "UNSUPPORTED": "non_supportato",
                    }.get(exc.code, "fallito")
                    results.append(Result(r.id, r.name, status, message=str(exc)))
                except OSError:
                    results.append(
                        Result(
                            r.id,
                            r.name,
                            "fallito",
                            message="Errore filesystem: verificare spazio e permessi.",
                        )
                    )
            report = {
                "version": 1,
                "created": datetime.now(timezone.utc).isoformat(),
                "counts": dict(Counter(r.status for r in results)),
                "results": [asdict(r) for r in results],
            }
            root.write_json(".fad/report.json", report)
            root.write(".fad/index.html", [index_html(manifest)])
            return report


def index_html(manifest):
    body = "<p>Raccolta locale. I file allegati non vengono eseguiti automaticamente.</p><ul>"
    for record in manifest["records"].values():
        components(record["path"])
        body += f'<li>{escape(record["course"])}: <a href="../{quote(record["path"])}">{escape(record["name"])}</a></li>'
    return html_page("FAD Downloader - Raccolta locale", body + "</ul>")


def verify(workspace):
    """Verifica read-only con digest indipendente dalla routine di trasferimento."""
    import hashlib

    root = SafeRoot(workspace)
    manifest = load_manifest(root)
    issues, checked = [], 0
    for record in manifest["records"].values():
        for item in [record, *record.get("assets", [])]:
            checked += 1
            try:
                digest, size = hashlib.sha256(), 0
                with root.open_read(item["path"]) as stream:
                    while block := stream.read(1024 * 1024):
                        digest.update(block)
                        size += len(block)
                if size != item["size"] or digest.hexdigest() != item["sha256"]:
                    issues.append(item["path"] + ": contenuto modificato")
            except (OSError, FadError):
                issues.append(item["path"] + ": non leggibile")
    return {"checked": checked, "issues": issues}
