import time
from unittest.mock import Mock

import pytest

from fad_downloader.demo import DEMO_ACCOUNT
from fad_downloader.domain import FadError
from fad_downloader.env_config import read_credentials, save_credentials


@pytest.mark.gui
def test_gui_reloads_and_saves_credentials_only_after_success(tmp_path, monkeypatch):
    import tkinter as tk
    from fad_downloader.gui import App

    path = tmp_path / ".env"
    save_credentials("previous", "previous-secret", path)
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("Display non disponibile")
    window.withdraw()
    app = App(window, env_file=path)
    moodle = Mock()
    moodle.login.return_value = DEMO_ACCOUNT
    monkeypatch.setattr("fad_downloader.gui.Moodle", lambda _: moodle)
    app.scan = lambda: None

    def drain():
        deadline = time.monotonic() + 10
        while app.future and time.monotonic() < deadline:
            window.update()
            time.sleep(0.01)
        assert app.future is None
        window.update()

    try:
        assert app.username.get() == "previous"
        assert app.password.get() == "previous-secret"
        app.username.set("new")
        app.password.set("new-secret")
        app.login()
        drain()
        assert read_credentials(path) == ("new", "new-secret")
        moodle.login.assert_called_with("new", "new-secret")
        moodle.login.side_effect = FadError("AUTH_REQUIRED", "rifiutato")
        app.password.set("wrong-secret")
        app.login()
        drain()
        assert read_credentials(path) == ("new", "new-secret")
        app.reload_credentials()
        assert app.password.get() == "new-secret"
        app.forget()
        drain()
        assert read_credentials(path) == ("", "")
        assert app.username.get() == app.password.get() == ""
    finally:
        if app.client:
            app.client.close()
        app.cancel.set()
        app.pool.shutdown(wait=True)
        window.destroy()
