"""CLI senza import di Tkinter; l'avvio senza sottocomandi apre la GUI."""

import argparse
from getpass import getpass
import json
from pathlib import Path
import sys
from threading import Event

from . import __version__
from .domain import FadError, Naming
from .services import Downloader, load_settings, plan, verify
from .storage import SafeRoot


def parser():
    p = argparse.ArgumentParser(description="FAD Downloader 0.0.1 - GNU/Linux")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--demo", action="store_true", help="GUI con dati sintetici offline")
    sub = p.add_subparsers(dest="command")
    for name in ("scan", "plan", "download", "verify", "report"):
        command = sub.add_parser(name)
        command.add_argument("--workspace", type=Path, default=Path.home() / "FAD")
        if name in {"scan", "plan", "download"}:
            command.add_argument("--demo", action="store_true")
            command.add_argument("--username")
            command.add_argument("--course-id", type=int, action="append")
            command.add_argument("--type", choices=("all", "materials", "quizzes"), default="all")
            command.add_argument("--non-interactive", action="store_true")
        if name == "download":
            command.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not args.command:
        from .gui import launch

        return launch(args.demo)
    client = None
    cancel = Event()
    try:
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
            from .credentials import CredentialStore
            from .moodle import Moodle
            from .network import HttpClient

            username = args.username
            if not username and not args.non_interactive:
                username = input("Username: ").strip()
            password = None
            if username:
                try:
                    password = CredentialStore().get(username)
                except FadError:
                    pass
            if not password and not args.non_interactive:
                password = getpass("Password: ")
            if not username or not password:
                raise FadError(
                    "AUTH_REQUIRED",
                    "Credenziali richieste: usare il login interattivo o il portachiavi.",
                )
            client = HttpClient(cancel)
            moodle = Moodle(client)
            account = moodle.login(username, password)
            password = None
            found = moodle.scan(lambda msg: print(msg, file=sys.stderr))
        resources = [
            r
            for r in found.resources
            if (not args.course_id or r.course_id in args.course_id)
            and (args.type == "all" or (r.kind == "quiz_review") == (args.type == "quizzes"))
        ]
        naming, mapping = load_settings(args.workspace)
        tasks = plan(resources, args.workspace, account, naming or Naming(), mapping)
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
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 3 if found.warnings and not args.demo else 0
        if not tasks:
            raise FadError("CONFIG", "Nessuna risorsa selezionata.")
        result = Downloader(client, account).run(tasks, args.workspace)
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
        cancel.set()
        return 130
    except FadError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 4 if exc.code == "AUTH_REQUIRED" else 2 if exc.code == "CONFIG" else 1
    except OSError:
        print("Errore filesystem: controllare percorso, permessi e spazio.", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
