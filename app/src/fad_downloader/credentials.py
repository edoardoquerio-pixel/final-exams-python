"""Backend espliciti: nessun fallback verso file plaintext."""

import sys

from .domain import FadError, ORIGIN
from .observability import monitored


class CredentialStore:
    @monitored("credentials.backend")
    def __init__(self):
        try:
            if sys.platform.startswith("linux"):
                from keyring.backends.SecretService import Keyring
            elif sys.platform == "win32":
                from keyring.backends.Windows import WinVaultKeyring as Keyring
            else:
                raise RuntimeError
            self.backend = Keyring()
            if self.backend.priority <= 0:
                raise RuntimeError
        except Exception:
            raise FadError(
                "KEYRING",
                "Portachiavi non disponibile. È possibile accedere senza salvare la password.",
            ) from None

    @monitored("credentials.read")
    def get(self, username):
        try:
            return self.backend.get_password("fad-downloader:" + ORIGIN, username)
        except Exception:
            raise FadError("KEYRING", "Impossibile leggere il portachiavi.") from None

    @monitored("credentials.save")
    def save(self, username, password):
        try:
            self.backend.set_password("fad-downloader:" + ORIGIN, username, password)
        except Exception:
            raise FadError(
                "KEYRING", "Accesso riuscito, ma password non salvata nel portachiavi."
            ) from None

    @monitored("credentials.delete")
    def delete(self, username):
        try:
            if self.get(username) is not None:
                self.backend.delete_password("fad-downloader:" + ORIGIN, username)
        except Exception:
            raise FadError("KEYRING", "Impossibile eliminare la credenziale.") from None
