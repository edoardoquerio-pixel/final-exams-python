import pytest

from fad_downloader.env_config import read_credentials, save_credentials
from fad_downloader.domain import FadError


def test_env_file_is_authoritative(tmp_path, monkeypatch):
    monkeypatch.delenv("FAD_USERNAME", raising=False)
    monkeypatch.delenv("FAD_PASSWORD", raising=False)
    path = tmp_path / ".env"
    path.write_text("FAD_USERNAME=' test '\nFAD_PASSWORD='a#${SECRET}$b'\n", encoding="utf-8")
    assert read_credentials(path) == ("test", "a#${SECRET}$b")
    monkeypatch.setenv("FAD_PASSWORD", "override")
    monkeypatch.setenv("FAD_USERNAME", "other_account")
    assert read_credentials(path) == ("test", "a#${SECRET}$b")


def test_missing_env_does_not_create_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FAD_USERNAME", raising=False)
    monkeypatch.delenv("FAD_PASSWORD", raising=False)
    path = tmp_path / ".env"
    assert read_credentials(path) == ("", "")
    assert not path.exists()


@pytest.mark.parametrize(
    "password", ["space # $ ${SECRET}", "a'b\\c\\'d", 'a"b', " leading and trailing ", "caf\u00e8"]
)
def test_save_and_reload_exact_password_preserves_other_settings(tmp_path, password):
    path = tmp_path / ".env"
    path.write_text(
        "# comment\nOTHER='unchanged'\nFAD_USERNAME='old'\nFAD_PASSWORD='old'\nFAD_USERNAME='duplicate'\n",
        encoding="utf-8",
    )
    save_credentials("student", password, path)
    assert read_credentials(path) == ("student", password)
    text = path.read_text(encoding="utf-8")
    assert "# comment" in text and "OTHER='unchanged'" in text
    assert text.count("FAD_USERNAME=") == 1
    assert text.count("FAD_PASSWORD=") == 1


def test_forget_clears_only_credential_keys(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OTHER=unchanged\n", encoding="utf-8")
    save_credentials("student", "secret", path)
    save_credentials("", "", path)
    assert read_credentials(path) == ("", "")
    assert "OTHER=unchanged" in path.read_text()


def test_invalid_input_does_not_overwrite_env(tmp_path):
    path = tmp_path / ".env"
    save_credentials("student", "original", path)
    original = path.read_bytes()
    with pytest.raises(FadError):
        save_credentials("student", "bad\npassword", path)
    assert path.read_bytes() == original
