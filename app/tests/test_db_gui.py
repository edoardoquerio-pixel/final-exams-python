import time

import pytest


@pytest.mark.gui
def test_register_switch_and_logout_database_users(tmp_path, monkeypatch):
    import tkinter as tk
    from fad_downloader.gui import App

    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("Display non disponibile")
    window.withdraw()
    app = App(window, env_file=tmp_path / ".env", database=tmp_path / "archive.sqlite3")

    def drain():
        deadline = time.monotonic() + 10
        while app.future and time.monotonic() < deadline:
            window.update()
            time.sleep(0.01)
        assert app.future is None

    try:
        for name, pw in (("alice", "AlicePassword!"), ("bob", "BobPassword!")):
            answers = iter([name, pw, pw])
            monkeypatch.setattr(
                "fad_downloader.gui.simpledialog.askstring", lambda *a, **kw: next(answers)
            )
            previous = app.db_session
            app.db_login(register=True)
            drain()
            assert app.db_session.username == name
            if previous:
                from fad_downloader.domain import FadError

                with pytest.raises(FadError):
                    app.archive.history(previous)
        app.db_logout()
        drain()
        assert app.db_session is None
    finally:
        app.pool.shutdown(wait=True)
        window.destroy()
