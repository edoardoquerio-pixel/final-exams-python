"""SQLite: utenti applicativi, download e contenuti BLOB a blocchi di 1 MiB."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import stat
import time
import uuid

from .domain import FadError, check_cancel
from .observability import event, monitored
from .storage import SafeRoot

SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
 salt BLOB NOT NULL, password_hash BLOB NOT NULL, created TEXT NOT NULL);
CREATE TABLE sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL);
CREATE TABLE runs (
 id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 account_key TEXT NOT NULL, created TEXT NOT NULL, finished TEXT, partial INTEGER NOT NULL DEFAULT 1);
CREATE TABLE downloads (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), user_id INTEGER NOT NULL REFERENCES users(id),
 resource_id TEXT NOT NULL, name TEXT NOT NULL, course TEXT NOT NULL, kind TEXT NOT NULL,
 status TEXT NOT NULL, message TEXT NOT NULL DEFAULT '');
CREATE TABLE objects (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 sha256 TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>=0),
 UNIQUE(user_id,sha256,size));
CREATE TABLE object_chunks (
 object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(object_id,position));
CREATE TABLE download_files (
 download_id INTEGER NOT NULL REFERENCES downloads(id), object_id INTEGER NOT NULL REFERENCES objects(id),
 relative_path TEXT NOT NULL, is_primary INTEGER NOT NULL,
 PRIMARY KEY(download_id,relative_path));
CREATE INDEX idx_downloads_user ON downloads(user_id,id);
CREATE INDEX idx_runs_user ON runs(user_id,created);
PRAGMA user_version=1;
COMMIT;
"""


@dataclass(frozen=True)
class UserSession:
    user_id: int
    username: str
    token: str = field(repr=False)


def now():
    return datetime.now(timezone.utc).isoformat()


def default_database_path(demo=False):
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "fad-downloader" / ("demo.sqlite3" if demo else "archive.sqlite3")


class Archive:
    def __init__(self, path=None, demo=False):
        self.path = (Path(path) if path is not None else default_database_path(demo)).absolute()
        SafeRoot(self.path.parent, create=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        except FileExistsError:
            if self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode):
                raise FadError("DB", "Il database deve essere un file regolare.")
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise FadError("DB", "Database estraneo: scegliere un nuovo file SQLite.")
                db.executescript(SCHEMA)
            elif version != 1:
                raise FadError("DB", "Versione del database non supportata.")
            db.execute(
                "CREATE TABLE IF NOT EXISTS metadata(name TEXT PRIMARY KEY,value TEXT NOT NULL)"
            )
            db.execute("INSERT OR IGNORE INTO metadata VALUES('identity',?)", (uuid.uuid4().hex,))
            db.execute("INSERT OR IGNORE INTO metadata VALUES('demo',?)", ("1" if demo else "0",))
            self.identity = db.execute(
                "SELECT value FROM metadata WHERE name='identity'"
            ).fetchone()[0]
            self.is_demo = (
                db.execute("SELECT value FROM metadata WHERE name='demo'").fetchone()[0] == "1"
            )
            if demo != self.is_demo:
                raise FadError("DB", "Database demo e database reale devono restare separati.")
            db.commit()
            db.execute("PRAGMA journal_mode=WAL")
        event("db.ready", demo=demo)

    @contextmanager
    def connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            try:
                yield db
                db.commit()
            finally:
                if db.in_transaction:
                    db.rollback()
        except sqlite3.Error:
            raise FadError(
                "DB", "Operazione SQLite non completata: controllare integrità, spazio e permessi."
            ) from None
        finally:
            if db:
                db.close()

    @staticmethod
    def _password(password, salt):
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)

    @monitored("db.user_register")
    def register(self, username, password):
        username = username.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
            raise FadError(
                "USER", "Nome utente DB non valido: usa 3-40 lettere a-z, numeri o . _ -, senza spazi né accenti."
            )
        if not 8 <= len(password) <= 1024:
            raise FadError("USER", "Password DB non valida: deve contenere da 8 a 1024 caratteri.")
        salt = secrets.token_bytes(16)
        digest = self._password(password, salt)
        with self.connect() as db:
            inserted = db.execute(
                "INSERT INTO users(username,salt,password_hash,created) VALUES(?,?,?,?) "
                "ON CONFLICT(username) DO NOTHING",
                (username, salt, digest, now()),
            )
            if inserted.rowcount == 0:
                raise FadError("USER", "Nome utente DB già utilizzato.")

    @monitored("db.user_login")
    def login(self, username, password):
        username = username.strip().casefold()
        if len(password) > 1024:
            raise FadError("AUTH_REQUIRED", "Credenziali utente DB non valide.")
        with self.connect() as db:
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, username, salt, password_hash FROM users WHERE username=?",
                (username,),
            )
            user = cursor.fetchone()
            digest = self._password(password, user["salt"] if user else b"\0" * 16)
            if not user or not hmac.compare_digest(digest, user["password_hash"]):
                raise FadError("AUTH_REQUIRED", "Credenziali utente DB non valide.")
            token = secrets.token_urlsafe(32)
            db.execute("DELETE FROM sessions WHERE expires<?", (int(time.time()),))
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), user["id"], int(time.time()) + 28800),
            )
            return UserSession(user["id"], user["username"], token)

    def _user(self, db, session):
        if not isinstance(session, UserSession):
            raise FadError("AUTH_REQUIRED", "Accedere come utente DB.")
        row = db.execute(
            "SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>=?",
            (hashlib.sha256(session.token.encode()).hexdigest(), int(time.time())),
        ).fetchone()
        if not row or row["id"] != session.user_id or row["username"] != session.username:
            raise FadError("AUTH_REQUIRED", "Sessione utente DB scaduta: accedere nuovamente.")
        return row["id"]

    def logout(self, session):
        if session:
            with self.connect() as db:
                db.execute(
                    "DELETE FROM sessions WHERE token_hash=?",
                    (hashlib.sha256(session.token.encode()).hexdigest(),),
                )
            event("db.user_logout")

    def validate_session(self, session):
        with self.connect() as db:
            return self._user(db, session)

    def demo_session(self):
        """Due utenti ordinari, soltanto nel database demo separato."""
        if not self.is_demo:
            raise FadError("DB", "Account dimostrativi consentiti solo nel database demo.")
        for username, password in (
            ("studente1", "DemoStudente1!"),
            ("studente2", "DemoStudente2!"),
        ):
            with self.connect() as db:
                exists = db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
            if not exists:
                self.register(username, password)
        return self.login("studente1", "DemoStudente1!")

    def start_run(self, session, account):
        account_key = account if isinstance(account, str) else account.key
        if self.is_demo:
            from .demo import DEMO_ACCOUNT

            if account_key != DEMO_ACCOUNT.key:
                raise FadError(
                    "DB", "Il database demo accetta soltanto contenuti del workspace demo."
                )
        if not re.fullmatch(r"[a-f0-9]{64}", account_key):
            raise FadError("DB", "Identificativo account non valido.")
        with self.connect() as db:
            uid = self._user(db, session)
            run_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO runs(id,user_id,account_key,created) VALUES(?,?,?,?)",
                (run_id, uid, account_key, now()),
            )
            return run_id

    def _run(self, db, uid, run_id):
        if not db.execute("SELECT 1 FROM runs WHERE id=? AND user_id=?", (run_id, uid)).fetchone():
            raise FadError("USER", "Download non appartenente all'utente DB.")

    @monitored("db.archive_resource")
    def record(self, session, run_id, resource, result, root, record=None, cancel=None):
        with self.connect() as db:
            uid = self._user(db, session)
            self._run(db, uid, run_id)
            cursor = db.execute(
                "INSERT INTO downloads(run_id,user_id,resource_id,name,course,kind,status,message) VALUES(?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    uid,
                    resource.id,
                    resource.name,
                    resource.course,
                    resource.kind,
                    result.status,
                    result.message,
                ),
            )
            download_id = cursor.lastrowid
            if record:
                for index, item in enumerate([record, *record.get("assets", [])]):
                    if cancel:
                        check_cancel(cancel)
                    existing = db.execute(
                        "SELECT id FROM objects WHERE user_id=? AND sha256=? AND size=?",
                        (uid, item["sha256"], item["size"]),
                    ).fetchone()
                    object_id = (
                        existing["id"]
                        if existing
                        else db.execute(
                            "INSERT INTO objects(user_id,sha256,size) VALUES(?,?,?)",
                            (uid, item["sha256"], item["size"]),
                        ).lastrowid
                    )
                    digest = hashlib.sha256()
                    size = 0
                    position = 0
                    with root.open_read(item["path"]) as stream:
                        block = stream.read(1024 * 1024)
                        while block:
                            if cancel:
                                check_cancel(cancel)
                            digest.update(block)
                            size += len(block)
                            if not existing:
                                db.execute(
                                    "INSERT INTO object_chunks VALUES(?,?,?)",
                                    (object_id, position, sqlite3.Binary(block)),
                                )
                            position += 1
                            block = stream.read(1024 * 1024)
                    if size != item["size"] or digest.hexdigest() != item["sha256"]:
                        raise FadError(
                            "CONFLICT",
                            "File modificato durante l'archiviazione DB: transazione annullata.",
                        )
                    db.execute(
                        "INSERT INTO download_files VALUES(?,?,?,?)",
                        (download_id, object_id, item["path"], index == 0),
                    )
            event(
                "db.resource_archived",
                resource_id=resource.id[:12],
                status=result.status,
                files=(1 + len(record.get("assets", []))) if record else 0,
            )

    def finish_run(self, session, run_id, partial):
        with self.connect() as db:
            uid = self._user(db, session)
            self._run(db, uid, run_id)
            db.execute(
                "UPDATE runs SET finished=?,partial=? WHERE id=? AND user_id=?",
                (now(), bool(partial), run_id, uid),
            )

    @monitored("db.import_workspace")
    def import_workspace(self, session, workspace):
        from .domain import Resource, Result
        from .storage import load_manifest

        root = SafeRoot(Path(workspace))
        imported, failed = 0, 0
        with root.lock():
            manifest = load_manifest(root)
            if manifest.get("db_user_id") is not None and (
                manifest["db_user_id"] != session.user_id
                or manifest.get("db_identity") != self.identity
            ):
                raise FadError("USER", "Workspace associato a un altro utente DB.")
            run_id = self.start_run(session, manifest["account"])
            for rid, record in manifest["records"].items():
                resource = Resource(
                    rid,
                    0,
                    record.get("course", "Corso"),
                    "Archivio esistente",
                    0,
                    record.get("name", "File"),
                    record.get("kind", "file"),
                    "",
                )
                result = Result(
                    rid,
                    resource.name,
                    "importato",
                    record["path"],
                    "Importazione locale: data originale non ricostruita.",
                )
                try:
                    self.record(session, run_id, resource, result, root, record)
                    imported += 1
                except (FadError, OSError) as exc:
                    if isinstance(exc, FadError) and exc.code not in {"CONFLICT", "PATH"}:
                        raise
                    failed += 1
                    result.status = "fallito"
                    result.message = "File locale mancante o modificato: BLOB non importato."
                    self.record(session, run_id, resource, result, root)
            self.finish_run(session, run_id, bool(failed))
            manifest.update(db_user_id=session.user_id, db_identity=self.identity)
            root.write_json(".fad/manifest.json", manifest)
        return {"imported": imported, "failed": failed, "db_run_id": run_id}

    @monitored("db.history")
    def history(self, session):
        with self.connect() as db:
            uid = self._user(db, session)
            rows = db.execute(
                "SELECT d.*,r.created,r.finished,r.partial,COUNT(f.object_id) file_count,COALESCE(SUM(o.size),0) size FROM downloads d JOIN runs r ON r.id=d.run_id LEFT JOIN download_files f ON f.download_id=d.id LEFT JOIN objects o ON o.id=f.object_id AND o.user_id=d.user_id WHERE d.user_id=? GROUP BY d.id ORDER BY d.id DESC",
                (uid,),
            ).fetchall()
            return [dict(r) for r in rows]

    def files(self, session, download_id):
        with self.connect() as db:
            uid = self._user(db, session)
            return [
                dict(r)
                for r in db.execute(
                    "SELECT f.object_id,f.relative_path,f.is_primary,o.size,o.sha256 FROM download_files f JOIN downloads d ON d.id=f.download_id JOIN objects o ON o.id=f.object_id AND o.user_id=d.user_id WHERE d.id=? AND d.user_id=? ORDER BY f.is_primary DESC",
                    (download_id, uid),
                )
            ]

    @monitored("db.restore_object")
    def restore(self, session, object_id, destination):
        destination = Path(destination).absolute()
        root = SafeRoot(destination.parent)
        with self.connect() as db:
            uid = self._user(db, session)
            item = db.execute(
                "SELECT * FROM objects WHERE id=? AND user_id=?", (object_id, uid)
            ).fetchone()
            if not item:
                raise FadError("USER", "Oggetto non disponibile per questo utente DB.")

            def chunks():
                digest, size = hashlib.sha256(), 0
                for row in db.execute(
                    "SELECT data FROM object_chunks WHERE object_id=? ORDER BY position",
                    (object_id,),
                ):
                    block = row[0]
                    digest.update(block)
                    size += len(block)
                    yield block
                if size != item["size"] or digest.hexdigest() != item["sha256"]:
                    raise FadError("DB", "BLOB corrotto: ripristino annullato.")

            root.write(destination.name, chunks(), expected=None)
