"""Credenziali locali: lettura senza modificare l'ambiente del processo."""

import hashlib
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values
from dotenv.parser import parse_stream

from .domain import FadError
from .observability import event, monitored
from .storage import SafeRoot


def default_env_path():
    project = Path(__file__).resolve().parents[2]
    return (project if (project / "pyproject.toml").is_file() else Path.cwd()) / ".env"


@monitored("credentials.env_read")
def read_credentials(path=None):
    path = Path(path) if path is not None else default_env_path()
    try:
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise FadError("CONFIG", "Il file .env deve essere un file regolare.")
            if path.stat().st_size > 65536:
                raise FadError("CONFIG", "File .env troppo grande.")
            values = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
        else:
            values = {}
    except (OSError, UnicodeError):
        raise FadError("CONFIG", "Impossibile leggere il file .env.") from None
    username = values.get("FAD_USERNAME") or ""
    password = values.get("FAD_PASSWORD") or ""
    event("credentials.env_available", stored=bool(username and password))
    return username.strip(), password


@monitored("credentials.env_save")
def save_credentials(username, password, path=None):
    """Aggiorna le due chiavi senza cancellare commenti o altre impostazioni."""
    username = username.strip()
    if any(c in username + password for c in ("\r", "\n", "\x00")):
        raise FadError("CONFIG", "Le credenziali non possono contenere ritorni a capo o NUL.")
    path = (Path(path) if path is not None else default_env_path()).absolute()
    root = SafeRoot(path.parent)
    try:
        original = root.read(path.name)
    except FileNotFoundError:
        original = None
    if original is not None and len(original) > 65536:
        raise FadError("CONFIG", "File .env troppo grande.")
    try:
        text = original.decode("utf-8-sig") if original is not None else ""
        bindings = list(parse_stream(StringIO(text)))
        if any(binding.error for binding in bindings):
            raise ValueError
    except (UnicodeError, ValueError):
        raise FadError(
            "CONFIG", "File .env non valido: correggerlo prima del salvataggio."
        ) from None
    retained = "".join(
        binding.original.string
        for binding in bindings
        if binding.key not in {"FAD_USERNAME", "FAD_PASSWORD"}
    )
    if retained and not retained.endswith("\n"):
        retained += "\n"

    def quote(value):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    content = (
        retained + "FAD_USERNAME=" + quote(username) + "\nFAD_PASSWORD=" + quote(password) + "\n"
    ).encode("utf-8")
    expected = (
        (len(original), hashlib.sha256(original).hexdigest()) if original is not None else None
    )
    try:
        root.write(path.name, [content], expected=expected)
    except OSError:
        raise FadError(
            "CONFIG",
            "Non è stato possibile salvare le credenziali nel file .env.",
        ) from None
    event("credentials.env_saved", stored=bool(username and password))
