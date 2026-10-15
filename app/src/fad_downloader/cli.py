"""CLI senza import di Tkinter; l'avvio senza sottocomandi apre la GUI."""

import argparse
from getpass import getpass
import json
from pathlib import Path
import sys
from threading import Event

from . import __version__
from .domain import FadError, Limits, Naming
from .services import Downloader, load_settings, plan, verify
from .storage import SafeRoot
from .observability import configure, event, failure, monitored


def parser():
    p = argparse.ArgumentParser(description="FAD Downloader 0.1.0 - GNU/Linux")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    p.add_argument("--log-dir", type=Path, help="Directory dei log JSON a rotazione")
    p.add_argument("--no-log", action="store_true", help="Disabilita i log su file")
    p.add_argument("--env-file", type=Path, help="File .env alternativo (prima del sottocomando)")
    p.add_argument("--demo", action="store_true", help="GUI con dati sintetici offline")
    p.add_argument("--file-limit", type=int, help="Limite file in byte")
    p.add_argument("--run-limit", type=int, help="Limite totale in byte")
    sub = p.add_subparsers(dest="command")
    for name in (
        "scan",
        "plan",
        "download",
        "verify",
        "report",
        "catalog",
        "backup",
        "restore",
        "recovery",
    ):
        command = sub.add_parser(name)
        command.add_argument("--workspace", type=Path)
        if name in {"scan", "plan", "download"}:
            command.add_argument("--demo", action="store_true")
            command.add_argument("--username")
            command.add_argument("--course-id", type=int, action="append")
            command.add_argument("--type", choices=("all", "materials", "quizzes"), default="all")
            command.add_argument("--non-interactive", action="store_true")
        if name == "download":
            command.add_argument("--dry-run", action="store_true")
            command.add_argument(
                "--resume", action="store_true", help="Recupera il piano interrotto"
            )
            command.add_argument(
                "--copy-conflicts",
                action="store_true",
                help="Pianifica copie alternative dei conflitti",
            )
        if name == "restore":
            command.add_argument(
                "--backup", required=True, help="Percorso .fad/backups/... da ripristinare"
            )
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        path = configure(args.log_level, args.log_dir, enabled=not args.no_log)
    except FadError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if path:
        print("Log: " + str(path), file=sys.stderr)
    event("app.start", command=args.command or "gui", demo=args.demo)
    result = _execute(args)
    event("app.exit", code=str(result))
    return result


@monitored("app.execute")
def _execute(args):
    if not args.command:
        from .gui import launch

        return launch(args.demo, args.env_file)
    client = None
    cancel = Event()
    try:
        from .state import (
            backup_state,
            load_catalog,
            load_pending,
            preferences,
            recovery_inventory,
            restore_state,
            save_catalog,
        )

        config = preferences() if args.command in {"scan", "plan", "download"} else {}
        if args.workspace is None:
            args.workspace = (
                Path.home() / "FAD-demo"
                if getattr(args, "demo", False)
                else Path(config.get("workspace", Path.home() / "FAD"))
            )
        limits_data = dict(config.get("limits", {}))
        if args.file_limit is not None:
            limits_data["file_bytes"] = args.file_limit
        if args.run_limit is not None:
            limits_data["run_bytes"] = args.run_limit
        limits = Limits(**limits_data)
        if args.command in {"catalog", "backup", "restore", "recovery"}:
            if args.command == "catalog":
                catalog, changes = load_catalog(args.workspace)
                result = {
                    "courses": [{"id": c.id, "name": c.name} for c in catalog.courses],
                    "resources": [
                        {"id": r.id, "name": r.name, "kind": r.kind} for r in catalog.resources
                    ],
                    "warnings": catalog.warnings,
                    "sections": [
                        {
                            "id": s.id,
                            "course_id": s.course_id,
                            "name": s.name,
                            "index": s.index,
                            "available": s.available,
                        }
                        for s in catalog.sections
                    ],
                    "changes": changes,
                }
            elif args.command == "backup":
                result = {"backup": backup_state(args.workspace)}
            elif args.command == "restore":
                result = {"restored": restore_state(args.workspace, args.backup)}
            else:
                result = recovery_inventory(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify":
            result = verify(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 3 if result["issues"] else 0
        if args.command == "report":
            result = SafeRoot(args.workspace).json(".fad/report.json")
            if result is None:
                raise FadError("STATE", "Nessun report presente.")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.demo:
            from .demo import DEMO_ACCOUNT, DemoHttp, catalog

            account, client, found = DEMO_ACCOUNT, DemoHttp(cancel), catalog()
        else:
            from .moodle import Moodle
            from .network import HttpClient

            from .env_config import read_credentials, save_credentials

            env_username, env_password = read_credentials(args.env_file)
            username = args.username or env_username
            if not username and not args.non_interactive:
                username = input("Username: ").strip()
            password = env_password if username == env_username else None
            if not password and not args.non_interactive:
                password = getpass("Password: ")
            if not username or not password:
                raise FadError(
                    "AUTH_REQUIRED",
                    "Credenziali richieste: compilare .env oppure usare il login interattivo.",
                )
            client = HttpClient(cancel, limits)
            moodle = Moodle(client)
            account = moodle.login(username, password)
            try:
                save_credentials(username, password, args.env_file)
            except (FadError, OSError):
                print("Accesso riuscito, ma credenziali non salvate nel .env.", file=sys.stderr)
            password = None
            found = moodle.scan(lambda msg: print(msg, file=sys.stderr))
        resources = [
            r
            for r in found.resources
            if (not args.course_id or r.course_id in args.course_id)
            and (args.type == "all" or (r.kind == "quiz_review") == (args.type == "quizzes"))
        ]
        naming, mapping = load_settings(args.workspace)
        if not (args.workspace / ".fad/settings.json").exists():
            naming = Naming(**config.get("naming", {}))
        tasks = plan(resources, args.workspace, account, naming or Naming(), mapping)
        if args.command == "download" and args.resume:
            tasks = load_pending(args.workspace, account)
        if args.command == "download" and args.copy_conflicts:
            from .services import alternate_tasks

            tasks = alternate_tasks(args.workspace, account)
        if args.command == "scan":
            save_catalog(args.workspace, account, found)
        if args.command != "download" or args.dry_run:
            # Nessun URL autenticato serializzato; l'anteprima non salva file.
            print(
                json.dumps(
                    {
                        "courses": [{"id": c.id, "name": c.name} for c in found.courses],
                        "tasks": [
                            {
                                "id": t.resource.id,
                                "name": t.resource.name,
                                "type": t.resource.kind,
                                "path": t.relative,
                            }
                            for t in tasks
                        ],
                        "warnings": found.warnings,
                        "sections": [
                            {
                                "id": s.id,
                                "course_id": s.course_id,
                                "name": s.name,
                                "available": s.available,
                            }
                            for s in found.sections
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 3 if found.warnings and not args.demo else 0
        if not tasks:
            raise FadError("CONFIG", "Nessuna risorsa selezionata.")
        save_catalog(args.workspace, account, found)

        def reauthenticate():
            new_username, new_password = read_credentials(args.env_file)
            if new_username != username:
                new_password = None
            if not new_password:
                raise FadError(
                    "AUTH_REQUIRED", "Nuovo accesso manuale richiesto; piano conservato."
                )
            try:
                return moodle.login(username, new_password)
            finally:
                new_password = None

        result = Downloader(client, account, None if args.demo else reauthenticate).run(
            tasks, args.workspace
        )
        for warning in found.warnings:
            print(("Demo: " if args.demo else "Scansione incompleta: ") + warning, file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return (
            3
            if (found.warnings and not args.demo)
            or any(
                x["status"] not in {"scaricato", "aggiornato", "invariato"}
                for x in result["results"]
            )
            else 0
        )
    except KeyboardInterrupt:
        event("app.interrupted")
        cancel.set()
        return 130
    except FadError as exc:
        failure("app.failed", exc)
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 4 if exc.code == "AUTH_REQUIRED" else 2 if exc.code == "CONFIG" else 1
    except OSError as exc:
        failure("app.filesystem_failed", exc)
        print("Errore filesystem: controllare percorso, permessi e spazio.", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
