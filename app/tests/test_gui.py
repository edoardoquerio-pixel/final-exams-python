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
    finally:
        app.cancel.set()
        app.pool.shutdown(wait=True)
        window.destroy()
