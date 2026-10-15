import time

import pytest


@pytest.mark.gui
def test_gui_demo_preview_download_verify(tmp_path):
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
        app.download()
        drain()
        assert (tmp_path / ".fad/index.html").is_file()
        app.verify_files()
        drain()
        assert "problemi: 0" in app.status.get()
        app.scan()
        drain()
        assert len(app.changes["new"]) == 3
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
