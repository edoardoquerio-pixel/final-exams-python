"""Pianificazione deterministica, download e report condivisi da GUI e CLI."""

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit
import uuid

from .domain import Account, FadError, Limits, Naming, Result, Task, check_cancel
from .exporter import export_bundle, html_page
from .storage import SafeRoot, clean_name, components, load_manifest, render_name
from .observability import event, failure, monitored

from .domain import SUPPORTED_RESOURCE_KINDS

SUPPORTED = SUPPORTED_RESOURCE_KINDS


@monitored("plan.build")
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
            "activity_name": clean_name(resource.activity_name or resource.name),
            "section_index": resource.section_index,
            "quiz_id": resource.activity_id,
            "attempt_id": resource.attempt_id or "0",
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
        activity = render_name(naming.activity, values)
        subfolder = resource.subfolder
        if subfolder:
            components(subfolder)
            subfolder += "/"
        relative = f"{course}/{section}/{category}/{activity}/{subfolder}{name}"
        record = records.get(resource.id)
        if record:
            relative = record.get("base", record["path"])
        components(relative)
        tasks.append(Task(resource, relative))
    event("plan.result", resources=len(tasks))
    return tasks


@monitored("settings.save")
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


@monitored("settings.load")
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
    def __init__(self, http, account, reauthenticate=None, archive=None, user_session=None):
        self.http, self.account = http, account
        self.archive, self.user_session = archive, user_session
        self.limits = getattr(http, "limits", Limits())
        self.reauthenticate = reauthenticate
        self.total_bytes = 0

    @monitored("download.transfer")
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
                current = root.fingerprint(relative)
                if before is None or current is None:
                    raise FadError("INVALID_CONTENT", "HTTP 304 senza copia valida.")
                if current != before:
                    raise FadError("CONFLICT", "File locale modificato durante la richiesta: conservato.")
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
                    if self.total_bytes > self.limits.run_bytes:
                        raise FadError("LIMIT", "Limite totale del download raggiunto.")
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

    @monitored("download.export")
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

    @monitored("download.run")
    def run(self, tasks, workspace, emit=lambda text: None):
        root = SafeRoot(workspace, create=True)
        results = []
        self.total_bytes = 0
        with root.lock():
            manifest = load_manifest(root, self.account)
            if self.archive:
                user_id = self.archive.validate_session(self.user_session)
                owner = manifest.get("db_user_id")
                if owner is not None and (
                    owner != user_id or manifest.get("db_identity") != self.archive.identity
                ):
                    raise FadError(
                        "USER",
                        "Workspace associato a un altro utente DB: scegliere una directory diversa.",
                    )
                manifest["db_user_id"] = user_id
                manifest["db_identity"] = self.archive.identity
            run_id = (
                self.archive.start_run(self.user_session, self.account) if self.archive else None
            )
            from .state import resource_data

            root.write_json(
                ".fad/pending.json",
                {
                    "version": 1,
                    "account": self.account.key,
                    "tasks": [
                        {"resource": resource_data(t.resource), "relative": t.relative}
                        for t in tasks
                    ],
                },
            )
            # Vincola il workspace anche se la prima operazione fallisce.
            root.write_json(".fad/manifest.json", manifest)
            auth_failed = False
            reauthenticated = False
            for task in tasks:
                r = task.resource
                record = None
                event("download.task_start", resource_id=r.id[:12], kind=r.kind)
                emit("Download: " + r.name)
                try:
                    check_cancel(self.http.cancel)
                    if auth_failed:
                        raise FadError("AUTH_REQUIRED", "Da ritentare dopo un nuovo login.")
                    if r.kind not in SUPPORTED:
                        raise FadError("UNSUPPORTED", "Tipo attività non supportato nella 0.0.1.")
                    old = manifest["records"].get(r.id)

                    def execute():
                        if r.kind == "file":
                            return self.transfer(root, r.url, task.relative, old, r.size)
                        return self.export(root, task, old)

                    try:
                        record, status = execute()
                    except FadError as exc:
                        if (
                            exc.code != "AUTH_REQUIRED"
                            or reauthenticated
                            or not self.reauthenticate
                        ):
                            raise
                        reauthenticated = True
                        event("auth.reauthenticate")
                        emit("Sessione scaduta: nuovo accesso in corso.")
                        account = self.reauthenticate()
                        if account.key != self.account.key:
                            raise FadError(
                                "ACCOUNT", "Riautenticazione con account diverso: piano sospeso."
                            )
                        record, status = execute()
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
                    event(
                        "download.task_result",
                        resource_id=r.id[:12],
                        status=status,
                        bytes=record["size"],
                    )
                except FadError as exc:
                    failure("download.task_failed", exc)
                    auth_failed |= exc.code in {"AUTH_REQUIRED", "ACCOUNT"}
                    status = {
                        "CANCELLED": "annullato",
                        "CONFLICT": "conflitto",
                        "UNSUPPORTED": "non_supportato",
                    }.get(exc.code, "fallito")
                    results.append(Result(r.id, r.name, status, message=str(exc)))
                except OSError as exc:
                    failure("download.filesystem_failed", exc)
                    results.append(
                        Result(
                            r.id,
                            r.name,
                            "fallito",
                            message="Errore filesystem: verificare spazio e permessi.",
                        )
                    )
                if self.archive:
                    try:
                        archived = (
                            record
                            if results[-1].status in {"scaricato", "aggiornato", "invariato"}
                            else None
                        )
                        self.archive.record(
                            self.user_session,
                            run_id,
                            r,
                            results[-1],
                            root,
                            archived,
                            self.http.cancel if archived else None,
                        )
                    except (FadError, OSError) as exc:
                        failure("db.archive_failed", exc)
                        results[-1].status = (
                            "annullato"
                            if isinstance(exc, FadError) and exc.code == "CANCELLED"
                            else "archiviazione_fallita"
                        )
                        results[
                            -1
                        ].message = "File locale conservato; archiviazione BLOB non completata. Ritentare il download."
            report = {
                "version": 1,
                "created": datetime.now(timezone.utc).isoformat(),
                "counts": dict(Counter(r.status for r in results)),
                "results": [asdict(r) for r in results],
            }
            catalog = root.json(".fad/catalog.json", {})
            report["scan_warnings"] = catalog.get("warnings", [])
            report["partial"] = bool(report["scan_warnings"]) or any(
                r.status not in {"scaricato", "aggiornato", "invariato"} for r in results
            )
            report["resources"] = len(results)
            report["files"] = sum(
                1 + len(manifest["records"].get(r.resource_id, {}).get("assets", []))
                for r in results
                if r.status in {"scaricato", "aggiornato", "invariato"}
            )
            failures = {
                r.resource_id
                for r in results
                if r.status in {"fallito", "annullato", "conflitto", "archiviazione_fallita"}
            }
            root.write_json(
                ".fad/pending.json",
                {
                    "version": 1,
                    "account": self.account.key,
                    "tasks": [
                        {"resource": resource_data(t.resource), "relative": t.relative}
                        for t in tasks
                        if t.resource.id in failures
                    ],
                },
            )
            if self.archive:
                self.archive.finish_run(self.user_session, run_id, report["partial"])
                report["db_run_id"] = run_id
            root.write_json(".fad/report.json", report)
            root.write(".fad/index.html", [index_html(manifest, root)])
            event(
                "download.result",
                resources=report["resources"],
                files=report["files"],
                partial=report["partial"],
                bytes=self.total_bytes,
            )
            return report


def index_html(manifest, root=None):
    groups = {}
    for record in manifest["records"].values():
        components(record["path"])
        exists = True
        if root:
            try:
                with root.open_read(record["path"]):
                    pass
            except (OSError, FadError):
                exists = False
        title = escape(record["name"])
        link = (
            f'<a href="../{quote(record["path"])}">{title}</a>'
            if exists
            else title + " (file locale mancante)"
        )
        state = record.get("remote_state", "presente")
        groups.setdefault(record["course"], []).append(f"<li>{link} — {escape(state)}</li>")
    body = "<p>Raccolta locale. I file allegati non vengono eseguiti automaticamente.</p>"
    for course, rows in sorted(groups.items()):
        body += "<h2>" + escape(course) + "</h2><ul>" + "".join(rows) + "</ul>"
    return html_page("FAD Downloader - Raccolta locale", body)


@monitored("integrity.verify")
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
                    block = stream.read(1024 * 1024)
                    while block:
                        digest.update(block)
                        size += len(block)
                        block = stream.read(1024 * 1024)
                if size != item["size"] or digest.hexdigest() != item["sha256"]:
                    issues.append(item["path"] + ": contenuto modificato")
            except (OSError, FadError):
                issues.append(item["path"] + ": non leggibile")
    event("integrity.result", files=checked, issues=len(issues))
    return {"checked": checked, "issues": issues}


def compare_catalog(catalog, workspace, account):
    """Confronta le risorse scaricabili della FAD con il manifest e i file presenti."""
    root = SafeRoot(workspace)
    manifest = load_manifest(root, account)
    result = verify(workspace)
    missing = []
    for resource in catalog.resources:
        if resource.kind not in SUPPORTED:
            continue
        record = manifest["records"].get(resource.id)
        if not record:
            missing.append(resource.name)
            continue
        if any(root.fingerprint(item["path"]) is None
               for item in [record, *record.get("assets", [])]):
            missing.append(resource.name)
    result["missing"] = missing
    return result


def alternate_tasks(workspace, account):
    """Nuove copie per i conflitti; la copia modificata non viene sovrascritta."""
    from dataclasses import replace
    from .state import load_pending
    from .domain import identifier

    root = SafeRoot(workspace)
    report = root.json(".fad/report.json", {})
    conflicts = {
        r["resource_id"] for r in report.get("results", []) if r.get("status") == "conflitto"
    }
    tasks = []
    for task in load_pending(workspace, account):
        if task.resource.id in conflicts:
            suffix = uuid.uuid4().hex[:12]
            new_id = identifier(task.resource.id + suffix)
            path = PurePosixPath(task.relative)
            destination = str(path.with_name(path.stem + "_copia_" + suffix + path.suffix))
            tasks.append(Task(replace(task.resource, id=new_id), destination))
    if not tasks:
        raise FadError("STATE", "Nessun conflitto recuperabile nel report.")
    return tasks
