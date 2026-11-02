"""Misure sintetiche: 1.000 risorse GUI e manifest con 10.000 record."""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import tkinter as tk

from fad_downloader.demo import DEMO_ACCOUNT, catalog
from fad_downloader.domain import Catalog, Naming, identifier
from fad_downloader.gui import App
from fad_downloader.services import plan
from fad_downloader.storage import SafeRoot, load_manifest


def main():
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    resources = [replace(catalog().resources[0], id=identifier(str(i)), activity_id=i + 1,
                         name=f"Risorsa {i}.txt") for i in range(1000)]
    root = SafeRoot(work / "workspace", create=True)
    record = {"path": "files/0.txt", "size": 0, "sha256": identifier(""), "kind": "file"}
    root.write_json(".fad/manifest.json", {"version": 1, "account": DEMO_ACCOUNT.key,
                    "records": {identifier(str(i)): dict(record, path=f"files/{i}.txt") for i in range(10000)}})
    measurements = {}

    def measure(name, function):
        started = time.perf_counter()
        value = function()
        measurements[name] = round((time.perf_counter() - started) * 1000, 2)
        return value

    assert len(measure("manifest_load_ms", lambda: load_manifest(root, DEMO_ACCOUNT))["records"]) == 10000
    assert len(measure("plan_ms", lambda: plan(resources, root.root, DEMO_ACCOUNT, Naming()))) == 1000
    window = tk.Tk()
    window.withdraw()
    app = App(window, demo=True, database=work / "demo.sqlite3")
    try:
        app.workspace.set(str(root.root))
        app.catalog = Catalog(courses=catalog().courses, resources=resources)
        app.changes = {"new": [r.id for r in resources]}
        measure("populate_ms", app.populate)
        assert len(app.nodes) == 1000
        measure("search_ms", lambda: app.search.set("Risorsa 999"))
        assert len(app.nodes) == 1
        app.search.set("")
        app.select_all()
        assert len(measure("selection_ms", app.selected)) == 1000
        assert app.messages.maxsize == 200
        measurements["ui_commands_within_200ms"] = all(measurements[k] <= 200 for k in ("populate_ms", "search_ms", "selection_ms"))
        destination = Path(__file__).resolve().parent / ".verification-artifacts/production-stress.json"
        destination.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
        print(json.dumps(measurements), flush=True)
    finally:
        app.cancel.set()
        app.pool.shutdown(wait=True)
        if app.db_session:
            app.archive.logout(app.db_session)
        window.destroy()


if __name__ == "__main__":
    main()
