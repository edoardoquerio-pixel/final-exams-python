"""Catalogo, piani recuperabili e backup; nessuna password o cookie persistiti."""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import uuid

from .domain import Catalog, Course, FadError, Limits, Naming, Resource, Section, Task, stable_url
from .network import validate_url
from .storage import SafeRoot, components, load_manifest
from .observability import monitored
from .domain import SUPPORTED_RESOURCE_KINDS
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def config_root():
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", base))
    return base / "fad-downloader"


@monitored("settings.global_load")
def preferences():
    path = config_root()
    if not path.exists():
        return {}
    data = SafeRoot(path).json("settings.json", {})
    if not isinstance(data, dict) or data.get("version", 1) != 1:
        raise FadError("CONFIG", "Configurazione globale non valida.")
    try:
        Limits(**data.get("limits", {}))
        naming = Naming(**data.get("naming", {}))
        if any(not isinstance(v, str) for v in asdict(naming).values()) or not isinstance(
            data.get("workspace", ""), str
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise FadError("CONFIG", "Configurazione globale non valida.") from None
    return data


@monitored("settings.global_save")
def save_preferences(workspace, naming, limits):
    root = SafeRoot(config_root(), create=True)
    with root.lock():
        root.write_json(
            "settings.json",
            {
                "version": 1,
                "workspace": str(workspace),
                "naming": asdict(naming),
                "limits": asdict(limits),
            },
        )


def validate_catalog_resource_url(resource):
    """Un riferimento a un'attività non supportata è metadato, non un permesso HTTP."""
    try:
        validate_url(resource.url)
        return
    except FadError as exc:
        if exc.code != "URL" or resource.kind in SUPPORTED_RESOURCE_KINDS:
            raise
    parts = urlsplit(resource.url)
    match = re.fullmatch(r"/mod/([a-z][a-z0-9_]*)/view\.php", parts.path)
    query = parse_qs(parts.query, keep_blank_values=True)
    ids = query.get("id", [])
    allowed = {"id", "redirect"} if resource.kind == "url" else {"id"}
    if (
        not match
        or match[1] != resource.kind
        or not set(query).issubset(allowed)
        or len(ids) != 1
        or not ids[0].isascii()
        or not ids[0].isdigit()
        or int(ids[0]) <= 0
    ):
        raise FadError("URL", "Riferimento attività non valido nel catalogo.")
    if "redirect" in query and query["redirect"] not in (["0"], ["1"]):
        raise FadError("URL", "Parametro attività non valido nel catalogo.")
    # Stessa origine, schema, porta e credenziali URL controllati dalla policy esistente.
    validate_url(
        urlunsplit((parts.scheme, parts.netloc, "/course/view.php", urlencode({"id": ids[0]}), ""))
    )


def resource_data(resource):
    data = asdict(resource)
    data["url"] = stable_url(resource.url)
    validate_catalog_resource_url(resource)
    return data


def decode_resources(values):
    if not isinstance(values, list) or len(values) > 100000:
        raise FadError("STATE", "Catalogo locale non valido.")
    result = []
    try:
        for value in values:
            resource = Resource(**value)
            if (
                not re.fullmatch(r"[a-f0-9]{64}", resource.id)
                or type(resource.course_id) is not int
                or type(resource.activity_id) is not int
            ):
                raise ValueError
            if any(
                not isinstance(v, str)
                for v in (
                    resource.name,
                    resource.course,
                    resource.section,
                    resource.kind,
                    resource.url,
                    resource.subfolder,
                )
            ):
                raise ValueError
            validate_catalog_resource_url(resource)
            if resource.subfolder:
                components(resource.subfolder)
            result.append(resource)
    except (TypeError, ValueError, KeyError):
        raise FadError("STATE", "Catalogo locale non valido.") from None
    return result


@monitored("state.catalog_save")
def save_catalog(workspace, account, catalog):
    # Prevalidazione prima di aggiornare il manifest o creare file di stato.
    resources = [resource_data(r) for r in catalog.resources]
    root = SafeRoot(workspace, create=True)
    with root.lock():
        manifest = load_manifest(root, account)
        previous = root.json(".fad/catalog.json", {})
        old = {r.id: r for r in decode_resources(previous.get("resources", []))}
        new = {r.id: r for r in catalog.resources}
        changes = {
            "new": list(new.keys() - old.keys()),
            "changed": [key for key in new.keys() & old.keys() if new[key] != old[key]],
            "not_seen": list(old.keys() - new.keys()),
            "partial": bool(catalog.warnings),
        }
        for key, record in manifest["records"].items():
            record["remote_state"] = (
                "presente"
                if key in new
                else "non_verificato"
                if catalog.warnings
                else "non_più_visibile"
            )
        root.write_json(".fad/manifest.json", manifest)
        root.write_json(
            ".fad/catalog.json",
            {
                "version": 1,
                "account": account.key,
                "scanned": datetime.now(timezone.utc).isoformat(),
                "courses": [asdict(c) for c in catalog.courses],
                "resources": resources,
                "sections": [asdict(s) for s in catalog.sections],
                "warnings": catalog.warnings,
                "changes": changes,
            },
        )
        return changes


@monitored("state.catalog_load")
def load_catalog(workspace, account=None):
    data = SafeRoot(workspace).json(".fad/catalog.json")
    if not isinstance(data, dict) or data.get("version") != 1:
        raise FadError("STATE", "Catalogo locale assente o non supportato.")
    if account and data.get("account") != account.key:
        raise FadError("ACCOUNT", "Catalogo di un altro account.")
    try:
        courses = [Course(**c) for c in data["courses"]]
        warnings = data["warnings"]
        if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
            raise ValueError
        sections = [Section(**s) for s in data.get("sections", [])]
        if any(
            not isinstance(s.id, str)
            or not isinstance(s.name, str)
            or type(s.course_id) is not int
            or type(s.index) is not int
            or s.index < 0
            for s in sections
        ):
            raise ValueError
        return Catalog(courses, decode_resources(data["resources"]), warnings, sections), data.get(
            "changes", {}
        )
    except (KeyError, TypeError, ValueError):
        raise FadError("STATE", "Catalogo locale corrotto.") from None


@monitored("state.plan_save")
def save_pending(workspace, account, tasks):
    root = SafeRoot(workspace, create=True)
    with root.lock():
        manifest = load_manifest(root, account)
        root.write_json(".fad/manifest.json", manifest)
        root.write_json(
            ".fad/pending.json",
            {
                "version": 1,
                "account": account.key,
                "tasks": [
                    {"resource": resource_data(t.resource), "relative": t.relative} for t in tasks
                ],
            },
        )


@monitored("state.plan_load")
def load_pending(workspace, account):
    root = SafeRoot(workspace)
    load_manifest(root, account)
    data = root.json(".fad/pending.json")
    if not isinstance(data, dict) or data.get("version") != 1 or data.get("account") != account.key:
        raise FadError("STATE", "Nessun piano recuperabile per questo account.")
    try:
        tasks = []
        for item in data["tasks"]:
            components(item["relative"])
            tasks.append(Task(decode_resources([item["resource"]])[0], item["relative"]))
        return tasks
    except (KeyError, TypeError):
        raise FadError("STATE", "Piano locale non valido.") from None


STATE_FILES = ("manifest.json", "settings.json", "catalog.json", "pending.json", "report.json")


@monitored("state.backup")
def backup_state(workspace):
    root = SafeRoot(workspace)
    with root.lock():
        folder = (
            ".fad/backups/"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "_"
            + uuid.uuid4().hex[:8]
        )
        for name in STATE_FILES:
            try:
                content = root.read(".fad/" + name)
            except FileNotFoundError:
                continue
            root.write(folder + "/" + name, [content])
        return folder


@monitored("state.restore")
def restore_state(workspace, folder):
    components(folder)
    if not re.fullmatch(r"\.fad/backups/[0-9]{8}T[0-9]{6}_[a-f0-9]{8}", folder):
        raise FadError("PATH", "Selezionare un backup interno al workspace.")
    root = SafeRoot(workspace)
    backup = SafeRoot(root.root / folder)
    restored = load_manifest(backup_manifest_root(backup))
    data = {name: backup.json(name) for name in STATE_FILES}
    for name, value in data.items():
        if value is not None and (not isinstance(value, dict) or value.get("version") != 1):
            raise FadError("STATE", "Schema del backup non supportato.")
        if value is not None and "account" in value and value["account"] != restored["account"]:
            raise FadError("ACCOUNT", "Backup con account incoerenti.")
    if data["catalog.json"] is not None:
        decode_resources(data["catalog.json"].get("resources"))
    if data["pending.json"] is not None:
        for task in data["pending.json"].get("tasks", []):
            components(task["relative"])
            decode_resources([task["resource"]])
    with root.lock():
        try:
            current = root.json(".fad/manifest.json")
        except FadError as exc:
            if exc.code != "STATE":
                raise
            current = None
        if isinstance(current, dict):
            if current.get("version") != 1:
                raise FadError("STATE", "Schema futuro: ripristino automatico rifiutato.")
            if current.get("account") != restored.get("account"):
                raise FadError("ACCOUNT", "Backup di un altro account.")
        rescue = (
            ".fad/backups/"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "_"
            + uuid.uuid4().hex[:8]
        )
        for name in STATE_FILES:
            try:
                content = root.read(".fad/" + name)
            except FileNotFoundError:
                continue
            root.write(rescue + "/" + name, [content])
        for name, value in data.items():
            if value is not None:
                root.write_json(".fad/" + name, value)
        from .services import index_html

        root.write(".fad/index.html", [index_html(restored, root)])
    return folder


def backup_manifest_root(backup):
    class View:
        def json(self, path, default=None):
            return backup.json(path.removeprefix(".fad/"), default)

    return View()


@monitored("state.recovery_inventory")
def recovery_inventory(workspace):
    root = SafeRoot(workspace)
    # Inventario soltanto: niente cancellazioni implicite di file dell'utente.
    temps, backups = [], []
    for current, directories, files in os.walk(root.root, followlinks=False):
        directories[:] = [d for d in directories if not (Path(current) / d).is_symlink()]
        for name in files:
            if re.fullmatch(r"\.part-[a-f0-9]{32}", name):
                temps.append((Path(current) / name).relative_to(root.root).as_posix())
    path = root.root / ".fad/backups"
    if path.is_dir() and not path.is_symlink():
        backups = [
            p.relative_to(root.root).as_posix()
            for p in path.iterdir()
            if p.is_dir() and not p.is_symlink()
        ]
    return {"temporary_files": temps, "backups": sorted(backups)}
