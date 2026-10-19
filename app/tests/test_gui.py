import time

import pytest


@pytest.mark.gui
def test_gui_demo_preview_download_verify(tmp_path, monkeypatch):
    import tkinter as tk
    from fad_downloader.gui import App

    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("Display non disponibile")
    window.withdraw()
    app = App(window, demo=True)
    app.workspace.set(str(tmp_path))

    def drain():
        deadline = time.monotonic() + 10
        while app.future and time.monotonic() < deadline:
            window.update()
            time.sleep(0.01)
        assert app.future is None

    try:
        app.select_all()
        window.update()
        app.preview_plan()
        drain()
        assert len(app.tasks) == 3
        app.tree.selection_set(())
        window.update()
        assert not app.tasks
        app.download()
        drain()
        assert (tmp_path / ".fad/index.html").is_file()
        assert len(app.archive.history(app.db_session)) == 3
        monkeypatch.setattr(
            "fad_downloader.gui.filedialog.asksaveasfilename",
            lambda **kw: str(tmp_path / "user-report.pdf"),
        )
        app.db_pdf()
        drain()
        assert (tmp_path / "user-report.pdf").read_bytes().startswith(b"%PDF")
        # Exercise both archive dialogs and the restore button, including assets.
        from tkinter import ttk

        app.db_history()
        drain()
        history = app.db_dialogs[-1]
        history_tree = next(w for w in history.winfo_children() if isinstance(w, ttk.Treeview))
        assert len(history_tree.get_children()) == 3
        history_tree.selection_set(history_tree.get_children()[0])
        next(w for w in history.winfo_children() if isinstance(w, ttk.Button)).invoke()
        drain()
        picker = app.db_dialogs[-1]
        files_tree = next(w for w in picker.winfo_children() if isinstance(w, ttk.Treeview))
        files = app.archive.files(app.db_session, int(history_tree.selection()[0]))
        for index, item in enumerate(files):
            destination = tmp_path / f"restored-{index}.bin"
            monkeypatch.setattr(
                "fad_downloader.gui.filedialog.asksaveasfilename",
                lambda destination=destination, **kw: str(destination),
            )
            files_tree.selection_set(str(index))
            next(w for w in picker.winfo_children() if isinstance(w, ttk.Button)).invoke()
            drain()
            assert destination.read_bytes() == (tmp_path / item["relative_path"]).read_bytes()
            assert "ripristinato" in app.status.get()
        app.close_db_views()
        app.verify_files()
        drain()
        assert "problemi: 0" in app.status.get()
        assert "Risorse mancanti: 0" in app.status.get()
        from fad_downloader.services import compare_catalog
        from fad_downloader.storage import SafeRoot, load_manifest

        record = next(iter(load_manifest(SafeRoot(tmp_path), app.account)["records"].values()))
        (tmp_path / record["path"]).unlink()
        comparison = compare_catalog(app.catalog, tmp_path, app.account)
        assert len(comparison["missing"]) == 1
        assert len(comparison["issues"]) == 1
        app.scan()
        drain()
        assert not app.changes["new"]  # Verification already saved the fresh FAD scan.
        app.catalog.resources = []
        app.open_catalog()
        drain()
        assert len(app.catalog.resources) == 3
        app.read_report()
        drain()
        app.backup()
        drain()
        assert "Backup" in app.status.get()
        from fad_downloader.domain import Section

        app.catalog.sections = [Section("1", 1, "Uguale", 1), Section("2", 1, "Uguale", 2)]
        app.populate()
        assert app.tree.exists("course:1:section:1")
        assert app.tree.exists("course:1:section:2")
        app.tree.selection_set("course:1:section:2")
        assert not app.selected()
    finally:
        app.cancel.set()
        app.pool.shutdown(wait=True)
        window.destroy()
