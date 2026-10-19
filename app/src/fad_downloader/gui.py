"""Interfaccia italiana Tkinter. Tutte le operazioni lente passano dal worker."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser
from .observability import event, failure, span

from .demo import DEMO_ACCOUNT, DemoHttp, catalog as demo_catalog
from .domain import Catalog, FadError, Limits, Naming
from .database import Archive
from .state import (
    backup_state,
    load_catalog,
    load_pending,
    preferences,
    recovery_inventory,
    restore_state,
    save_catalog,
    save_preferences,
)
from .moodle import Moodle
from .network import HttpClient
from .theme import apply_theme, style_text
from .services import Downloader, load_settings, plan, save_settings


class App:
    def __init__(self, window, demo=False, env_file=None, database=None):
        self.window, self.demo = window, demo
        from .env_config import default_env_path

        self.env_file = (Path(env_file) if env_file is not None else default_env_path()).absolute()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fad")
        self.messages = Queue(maxsize=200)
        self.cancel = Event()
        self.future = None
        self.finish = None
        self.closing = False
        self.client = None
        self.moodle = None
        self.account = None
        self.catalog = Catalog()
        self.mapping = {}
        self.changes = {}
        self.limits = Limits()
        self.login_username = ""
        self.tasks = []
        self.plan_revision = 0
        self.last_failed = set()
        self.archive = Archive(database, demo=demo)
        self.db_session = self.archive.demo_session() if demo else None
        self.db_dialogs = []
        self.db_label = tk.StringVar(
            value="Utente DB: " + (self.db_session.username if self.db_session else "nessuno")
        )
        self.buttons = []
        window.title("FAD Downloader 0.2.0" + (" - Demo offline" if demo else ""))
        window.geometry("1220x860")
        window.minsize(1050, 740)
        apply_theme(window)
        self.username, self.password = tk.StringVar(), tk.StringVar()
        if not demo:
            from .env_config import read_credentials

            try:
                username, password = read_credentials(self.env_file)
                self.username.set(username)
                self.password.set(password)
            except FadError:
                pass
        self.workspace = tk.StringVar(value=str(Path.home() / ("FAD-demo" if demo else "FAD")))
        self.search, self.type = tk.StringVar(), tk.StringVar(value="Tutti")
        self.course_template = tk.StringVar(value="{course_id}_{course_name}")
        self.section_template = tk.StringVar(value="{section_name}")
        self.materials, self.quizzes = tk.StringVar(value="Materiali"), tk.StringVar(value="Test")
        self.activity_template = tk.StringVar(value="{activity_id}_{activity_name}")
        if not demo:
            try:
                config = preferences()
                self.workspace.set(config.get("workspace", self.workspace.get()))
                self.limits = Limits(**config.get("limits", {}))
                defaults, self.mapping = load_settings(Path(self.workspace.get()))
                if not (Path(self.workspace.get()) / ".fad/settings.json").exists():
                    defaults = Naming(**config.get("naming", {}))
                for variable, key in (
                    (self.course_template, "course"),
                    (self.section_template, "section"),
                    (self.materials, "materials"),
                    (self.quizzes, "quizzes"),
                    (self.activity_template, "activity"),
                ):
                    variable.set(asdict(defaults)[key])
            except (FadError, TypeError, OSError):
                pass
        self.status = tk.StringVar(
            value="Demo offline" if demo else "Accedi alla FAD oppure apri una raccolta locale."
        )
        self.build()
        for var in (
            self.workspace,
            self.course_template,
            self.section_template,
            self.materials,
            self.quizzes,
            self.activity_template,
        ):
            var.trace_add("write", lambda *_: self.invalidate())
        self.search.trace_add("write", lambda *_: self.populate())
        self.type.trace_add("write", lambda *_: self.populate())
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.invalidate())
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.after(100, self.poll)
        if demo:
            self.client, self.account = DemoHttp(self.cancel), DEMO_ACCOUNT
            self.scanned(demo_catalog())

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command,
                            style="Primary.TButton" if text in {"Scarica", "Accedi"} else "TButton")
        button.pack(side="left", padx=3, pady=3)
        self.buttons.append(button)
        return button

    def build(self):
        shell = ttk.Frame(self.window, padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 20))
        ttk.Label(header, text="FAD Downloader", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="DEMO OFFLINE" if self.demo else "IL TUO ARCHIVIO DIDATTICO",
                  style="Badge.TLabel").pack(side="right")
        ttk.Label(shell, text="Corsi, materiali e test. Tutto nel tuo spazio di studio.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 18))
        menu = ttk.Frame(shell)
        menu.pack(fill="x", pady=(0, 24))
        self.section_popups = {}

        def section(title):
            popup = tk.Toplevel(self.window)
            popup.withdraw()
            popup.title(title)
            popup.transient(self.window)
            popup.overrideredirect(True)
            popup.configure(highlightthickness=1, highlightbackground="#D8E2ED")
            popup.resizable(True, False)
            popup.protocol("WM_DELETE_WINDOW", popup.withdraw)
            popup.bind("<Escape>", lambda _: popup.withdraw())
            self.section_popups[title] = popup

            def position(event=None):
                if event is not None and event.widget is not self.window:
                    return
                if popup.state() == "withdrawn":
                    return
                x = trigger.winfo_rootx()
                y = trigger.winfo_rooty() + trigger.winfo_height() + 6
                width = popup.winfo_reqwidth()
                x = max(0, min(x, popup.winfo_screenwidth() - width - 12))
                popup.geometry(f"+{x}+{y}")

            def show():
                if popup.state() != "withdrawn":
                    popup.withdraw()
                    return
                for other in self.section_popups.values():
                    other.withdraw()
                popup.deiconify()
                popup.update_idletasks()
                position()
                popup.lift()
                popup.focus_set()

            trigger = ttk.Button(menu, text=title, command=show)
            trigger.pack(side="left", padx=3)
            self.window.bind("<Configure>", position, add="+")

            def dismiss(event):
                if event.widget is not trigger:
                    popup.withdraw()

            self.window.bind("<Button-1>", dismiss, add="+")
            self.window.bind("<Escape>", lambda _: popup.withdraw(), add="+")
            self.window.bind("<Unmap>", lambda e: popup.withdraw()
                             if e.widget is self.window else None, add="+")
            return popup

        users = ttk.LabelFrame(
            section("Utenti database SQLite"),
            text="Utenti database SQLite (nessun amministratore)", padding=10
        )
        users.pack(fill="both", expand=True, padx=20, pady=20)
        ttk.Label(users, textvariable=self.db_label, style="Badge.TLabel").pack(anchor="w", pady=(8, 16))
        user_access = ttk.Frame(users)
        user_access.pack(anchor="w")
        self.button(user_access, "Accedi DB", lambda: self.db_login(False))
        self.button(user_access, "Registra utente DB", lambda: self.db_login(True))
        self.button(user_access, "Esci DB", self.db_logout)
        archive_actions = ttk.Frame(users)
        archive_actions.pack(anchor="w", pady=(8, 0))
        self.button(archive_actions, "Archivio BLOB", self.db_history)
        self.button(archive_actions, "Report PDF", self.db_pdf)
        self.button(archive_actions, "Importa workspace", self.db_import)
        login = ttk.LabelFrame(section("Accesso FAD"), text="Accesso FAD", padding=10)
        login.pack(fill="both", expand=True, padx=20, pady=20)
        for label, variable, masked in (("Username", self.username, False), ("Password", self.password, True)):
            ttk.Label(login, text=label).pack(anchor="w", pady=(12, 6))
            ttk.Entry(login, textvariable=variable, show="•" if masked else "", width=46).pack(fill="x")
        ttk.Label(login, text="Salvataggio automatico in .env", style="Subtitle.TLabel").pack(anchor="w", pady=12)
        login_actions = ttk.Frame(login)
        login_actions.pack(fill="x")
        self.button(login_actions, "Accedi", self.login)
        self.button(login_actions, "Carica .env", self.reload_credentials)
        session_actions = ttk.Frame(login)
        session_actions.pack(fill="x", pady=(8, 0))
        self.button(session_actions, "Esci account", self.logout)
        self.button(session_actions, "Dimentica password", self.forget)
        paths = ttk.LabelFrame(
            section("Cartelle e nomenclatura"), text="Cartelle e nomenclatura", padding=10
        )
        paths.pack(fill="both", expand=True, padx=20, pady=20)
        row = ttk.Frame(paths)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.workspace).pack(side="left", fill="x", expand=True)
        self.button(row, "Sfoglia", self.browse)
        self.button(row, "Carica impostazioni", self.read_settings)
        self.button(row, "Salva impostazioni", self.write_settings)
        grid = ttk.Frame(paths)
        grid.pack(fill="x", pady=4)
        for column, (label, var) in enumerate(
            (
                ("Corso", self.course_template),
                ("Sezione", self.section_template),
                ("Materiali", self.materials),
                ("Test", self.quizzes),
                ("Attività", self.activity_template),
            )
        ):
            ttk.Label(grid, text=label).grid(row=0, column=column, sticky="w")
            ttk.Entry(grid, textvariable=var).grid(row=1, column=column, sticky="ew", padx=3)
            grid.columnconfigure(column, weight=1)
        ttk.Label(
            paths,
            text="Segnaposto: {course_id}, {course_name}, {section_index}, {section_name}, {activity_id}, {activity_name}, {quiz_id}, {attempt_id}.",
        ).pack(anchor="w")
        actions = ttk.Frame(shell)
        ttk.Label(shell, text="La tua raccolta", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        actions.pack(fill="x")
        self.button(actions, "Scansiona FAD", self.scan)
        self.button(actions, "Seleziona tutto", self.select_all)
        self.button(actions, "Associa cartella", self.map_course)
        self.button(actions, "Limiti", self.edit_limits)
        ttk.Label(actions, text="Cerca").pack(side="left", padx=5)
        ttk.Entry(actions, textvariable=self.search, width=20).pack(side="left")
        ttk.Combobox(
            actions,
            textvariable=self.type,
            values=("Tutti", "Materiali", "Test"),
            state="readonly",
            width=12,
        ).pack(side="left", padx=5)
        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True, pady=6)
        catalog_frame = ttk.Frame(notebook)
        notebook.add(catalog_frame, text="Corsi e contenuti")
        self.tree = ttk.Treeview(catalog_frame, columns=("type",), selectmode="extended")
        self.tree.heading(
            "#0", text="Corsi, sezioni e attività"
        )
        self.tree.heading("type", text="Tipo")
        self.tree.column("type", width=190, stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(catalog_frame, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.preview = tk.Text(notebook, wrap="word", state="disabled", font=("TkFixedFont", 10))
        notebook.add(self.preview, text="Anteprima destinazioni")
        self.log = tk.Text(notebook, wrap="word", state="disabled")
        style_text(self.preview)
        style_text(self.log)
        notebook.add(self.log, text="Messaggi e report")
        controls = ttk.Frame(shell)
        controls.pack(fill="x", pady=(12, 4))
        self.button(controls, "Scarica", self.download)
        ttk.Button(controls, text="Annulla", command=self.cancel_work).pack(side="left", padx=3)
        self.button(controls, "Verifica file", self.verify_files)
        ttk.Label(controls, text="Nessuna selezione? Scarica l’intera raccolta.",
                  style="Subtitle.TLabel").pack(side="right", padx=8)
        self.progress = ttk.Progressbar(shell, mode="indeterminate")
        self.progress.pack(fill="x", pady=6)
        ttk.Label(shell, textvariable=self.status, style="Subtitle.TLabel",
                  wraplength=1100).pack(anchor="w", pady=(6, 0))

    def naming(self):
        return Naming(
            self.course_template.get(),
            self.section_template.get(),
            self.materials.get(),
            self.quizzes.get(),
            self.activity_template.get(),
        )

    def invalidate(self):
        self.tasks = []
        self.plan_revision += 1

    def emit(self, text):
        try:
            self.messages.put_nowait(text)
        except Full:
            pass  # Solo progresso sacrificabile; risultati terminali arrivano dal Future.

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 500:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self, function, finish):
        if self.future:
            return
        self.cancel.clear()
        self.finish = finish
        event("gui.worker_submitted")

        def work():
            with span("gui.worker"):
                return function()

        self.future = self.pool.submit(work)
        for button in self.buttons:
            button.configure(state="disabled")
        self.progress.start(15)
        self.status.set("Operazione in corso…")

    def poll(self):
        for _ in range(50):
            try:
                text = self.messages.get_nowait()
            except Empty:
                break
            if isinstance(text, Catalog):
                self.catalog = text
                self.populate()
            else:
                self.append(text)
                self.status.set(text)
        if self.future and self.future.done():
            future, finish = self.future, self.finish
            self.future = None
            self.progress.stop()
            for button in self.buttons:
                button.configure(state="normal")
            try:
                value = future.result()
                if not self.closing:
                    finish(value)
            except FadError as exc:
                failure("gui.operation_failed", exc)
                self.status.set(str(exc))
                self.append(f"{exc.code}: {exc}")
                if exc.code == "AUTH_REQUIRED":
                    self.append(
                        "Il piano è conservato: accedi allo stesso account e premi Recupera piano."
                    )
            except Exception as exc:
                failure("gui.unexpected_error", exc)
                self.status.set(
                    "Operazione non completata. Controllare configurazione, spazio e compatibilità Moodle."
                )
                self.append("Errore inatteso. Nessuna credenziale è stata scritta nei log.")
        if self.closing and not self.future:
            if self.client:
                self.client.close()
            if self.db_session:
                try:
                    self.archive.logout(self.db_session)
                except FadError as exc:
                    failure("db.logout_failed", exc)
            self.pool.shutdown(wait=False)
            self.window.destroy()
            return
        self.window.after(100, self.poll)

    def login(self):
        if self.demo:
            self.status.set(
                "Modalità demo offline: avvia senza --demo per accedere alla FAD reale."
            )
            return
        username, password = (
            self.username.get().strip(),
            self.password.get(),
        )
        try:
            from .env_config import read_credentials, save_credentials

            env_username, env_password = read_credentials(self.env_file)
        except FadError as exc:
            self.status.set(str(exc))
            return
        username = username or env_username
        if not password and username == env_username:
            password = env_password
        env_password = None
        if not username:
            self.status.set("Inserisci lo username.")
            return
        self.invalidate()
        self.catalog = Catalog()
        self.populate()
        self.account = None

        def work():
            nonlocal password
            if self.client:
                self.client.close()
            if not password:
                raise FadError("AUTH_REQUIRED", "Password richiesta.")
            self.client = HttpClient(self.cancel, self.limits)
            self.moodle = Moodle(self.client)
            try:
                account = self.moodle.login(username, password)
                try:
                    save_credentials(username, password, self.env_file)
                except (FadError, OSError):
                    self.emit(
                        "Accesso riuscito, ma credenziali non salvate nel .env. Controlla percorso e permessi."
                    )
                return account, username
            finally:
                password = None

        self.start(work, self.logged_in)

    def logged_in(self, value):
        account, self.login_username = value
        self.account, self.demo = account, False
        self.status.set("Accesso riuscito. Scansione iniziale in corso.")
        self.window.after_idle(self.scan)

    def logout(self):
        if self.moodle:
            moodle = self.moodle

            def work():
                try:
                    moodle.logout()
                    return True
                except FadError:
                    return False

            def finish(remote):
                self.clear_session()
                if not remote:
                    self.status.set("Sessione locale chiusa; logout remoto non confermato.")

            self.start(work, finish)
            return
        self.clear_session()

    def clear_session(self):
        if self.client:
            self.client.close()
        self.account, self.moodle, self.client = None, None, None
        self.password.set("")
        self.catalog, self.mapping = Catalog(), {}
        self.changes = {}
        self.login_username = ""
        self.populate()
        self.status.set("Sessione locale chiusa.")

    def forget(self):
        if self.demo:
            self.status.set("La demo non modifica le credenziali salvate.")
            return
        from .env_config import save_credentials

        def finish(_):
            self.username.set("")
            self.password.set("")
            self.status.set("Credenziali eliminate dal file .env.")

        self.start(lambda: save_credentials("", "", self.env_file), finish)

    def reload_credentials(self):
        from .env_config import read_credentials

        try:
            username, password = read_credentials(self.env_file)
        except FadError as exc:
            self.status.set(str(exc))
            return
        self.username.set(username)
        self.password.set(password)
        self.status.set("Credenziali caricate dal .env; premi Accedi.")

    def scan(self):
        if not self.account:
            self.status.set("Accedi prima di scansionare.")
            return
        workspace, account = Path(self.workspace.get()), self.account

        def work():
            catalog = demo_catalog() if self.demo else self.moodle.scan(self.emit, self.emit)
            changes = save_catalog(workspace, account, catalog)
            return catalog, changes

        self.start(work, self.scanned)

    def scanned(self, catalog):
        if isinstance(catalog, tuple):
            catalog, self.changes = catalog
        self.catalog = catalog
        self.populate()
        for warning in catalog.warnings:
            self.append(warning)
        if self.changes.get("not_seen"):
            self.append(
                f"Risorse non rilevate: {len(self.changes['not_seen'])}. Le copie locali vengono conservate."
            )
        self.status.set(
            f"{len(catalog.courses)} corsi, {len(catalog.sections)} sezioni, {len(catalog.resources)} risorse. Seleziona i contenuti e genera l'anteprima."
        )

    def populate(self):
        self.invalidate()
        self.tree.delete(*self.tree.get_children())
        self.nodes = {}
        search, mode = self.search.get().casefold(), self.type.get()
        if mode == "Tutti":
            for course in self.catalog.courses:
                if not search or search in course.name.casefold():
                    self.tree.insert(
                        "", "end", iid="course:" + str(course.id), text=course.name, open=True
                    )
            courses = {c.id: c for c in self.catalog.courses}
            for section in self.catalog.sections:
                course = courses.get(section.course_id)
                if not course or (search and search not in (course.name + section.name).casefold()):
                    continue
                parent = "course:" + str(section.course_id)
                if not self.tree.exists(parent):
                    self.tree.insert("", "end", iid=parent, text=course.name, open=True)
                self.tree.insert(
                    parent,
                    "end",
                    iid=parent + ":section:" + section.id,
                    text=section.name,
                    values=("Sezione" if section.available else "Non disponibile",),
                    open=True,
                )
        for resource in self.catalog.resources:
            if (
                search
                and search not in (resource.name + resource.course + resource.section).casefold()
            ):
                continue
            if mode != "Tutti" and (resource.kind == "quiz_review") != (mode == "Test"):
                continue
            course_id = "course:" + str(resource.course_id)
            section_id = (
                course_id + ":section:" + resource.section_id
                if resource.section_id
                else course_id + ":" + resource.section
            )
            if not self.tree.exists(course_id):
                self.tree.insert("", "end", iid=course_id, text=resource.course, open=True)
            if not self.tree.exists(section_id):
                self.tree.insert(course_id, "end", iid=section_id, text=resource.section, open=True)
            self.tree.insert(
                section_id,
                "end",
                iid=resource.id,
                text=resource.name,
                values=(
                    resource.kind
                    + (
                        " · nuovo"
                        if resource.id in self.changes.get("new", [])
                        else " · aggiornato"
                        if resource.id in self.changes.get("changed", [])
                        else ""
                    ),
                ),
            )
            self.nodes[resource.id] = resource

    def selected(self):
        ids = set()

        def walk(node):
            if node in self.nodes:
                ids.add(node)
            for child in self.tree.get_children(node):
                walk(child)

        for node in self.tree.selection():
            walk(node)
        return [r for r in self.catalog.resources if r.id in ids]

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def browse(self):
        selected = filedialog.askdirectory(title="Directory di lavoro")
        if selected:
            self.workspace.set(selected)

    def map_course(self):
        selected = self.selected()
        if not selected:
            self.status.set("Seleziona un corso o una sua attività.")
            return
        course_id = str(selected[0].course_id)
        folder = simpledialog.askstring(
            "Associazione corso",
            "Cartella relativa per " + selected[0].course,
            initialvalue=self.mapping.get(course_id, ""),
        )
        if folder:
            from .storage import components

            try:
                components(folder)
            except FadError as exc:
                self.status.set(str(exc))
                return
            self.mapping[course_id] = folder
            self.invalidate()
            self.status.set("Associazione aggiornata; salva le impostazioni per conservarla.")

    def read_settings(self):
        workspace = Path(self.workspace.get())

        def finish(value):
            naming, self.mapping = value
            for var, key in (
                (self.course_template, "course"),
                (self.section_template, "section"),
                (self.materials, "materials"),
                (self.quizzes, "quizzes"),
                (self.activity_template, "activity"),
            ):
                var.set(asdict(naming)[key])
            self.status.set("Impostazioni caricate.")

        self.start(lambda: load_settings(workspace), finish)

    def write_settings(self):
        if not self.account:
            self.status.set("Accedi prima di associare il workspace.")
            return
        workspace, naming, mapping, account = (
            Path(self.workspace.get()),
            self.naming(),
            dict(self.mapping),
            self.account,
        )
        limits = self.limits

        def work():
            save_settings(workspace, account, naming, mapping)
            if not self.demo:
                save_preferences(workspace, naming, limits)

        self.start(
            work,
            lambda _: self.status.set("Impostazioni salvate."),
        )

    def preview_plan(self):
        selected = self.selected()
        if not self.account or not selected:
            self.status.set("Accedi e seleziona almeno una risorsa.")
            return
        workspace, account, naming, mapping = (
            Path(self.workspace.get()),
            self.account,
            self.naming(),
            dict(self.mapping),
        )
        revision = self.plan_revision

        def finish(tasks):
            if revision != self.plan_revision:
                self.status.set("Selezione o impostazioni cambiate: rigenera l'anteprima.")
                return
            self.tasks = tasks
            self.planned_workspace = workspace
            self.preview.configure(state="normal")
            self.preview.delete("1.0", "end")
            self.preview.insert(
                "end", "\n\n".join(f"{t.resource.name}\n  → {t.relative}" for t in tasks)
            )
            self.preview.configure(state="disabled")
            self.status.set(f"Piano pronto: {len(tasks)} risorse. Nessun file scaricato.")

        self.start(lambda: plan(selected, workspace, account, naming, mapping), finish)

    def download(self):
        if not self.db_session:
            self.status.set("Accedi o registra un utente DB prima di scaricare.")
            return
        if not self.account or not self.client:
            self.status.set(
                "Accedi prima di scaricare; il catalogo offline è consultabile senza login."
            )
            return
        resources = self.selected() if self.tree.selection() else list(self.catalog.resources)
        if not resources:
            self.status.set("Nessuna risorsa da scaricare. Scansiona la FAD.")
            return
        client, account, workspace = (
            self.client,
            self.account,
            Path(self.workspace.get()),
        )
        naming, mapping = self.naming(), dict(self.mapping)
        self.start(
            lambda: Downloader(
                client,
                account,
                None if self.demo else self.reauthenticate,
                self.archive,
                self.db_session,
            ).run(plan(resources, workspace, account, naming, mapping), workspace, self.emit),
            self.downloaded,
        )

    def downloaded(self, report):
        self.last_failed = {
            r["resource_id"]
            for r in report["results"]
            if r["status"] in {"fallito", "annullato", "conflitto", "archiviazione_fallita"}
        }
        for result in report["results"]:
            self.append(f"{result['status']}: {result['name']} {result['message']}")
        self.status.set(" | ".join(f"{k}: {v}" for k, v in report["counts"].items()))

    def retry(self):
        nodes = [key for key in self.last_failed if self.tree.exists(key)]
        self.tree.selection_set(nodes)
        self.preview_plan()

    def verify_files(self):
        if not self.account:
            self.status.set("Accedi alla FAD prima di confrontare i file locali.")
            return
        workspace = Path(self.workspace.get())
        account = self.account

        def work():
            from .services import compare_catalog

            catalog = demo_catalog() if self.demo else self.moodle.scan(self.emit, self.emit)
            changes = save_catalog(workspace, account, catalog)
            result = compare_catalog(catalog, workspace, account)
            result["changed"] = changes.get("changed", [])
            return catalog, changes, result

        def finish(value):
            catalog, changes, result = value
            self.scanned((catalog, changes))
            self.status.set(
                f"Verificati {result['checked']} file; problemi: {len(result['issues'])}. "
                f"Risorse mancanti: {len(result['missing'])}; aggiornate sulla FAD: {len(result['changed'])}."
            )
            for name in result["missing"]:
                self.append("Da scaricare: " + name)
            for issue in result["issues"]:
                self.append(issue)
            for warning in catalog.warnings:
                self.append("Verifica parziale: " + warning)

        self.start(work, finish)

    def open_index(self):
        path = Path(self.workspace.get()) / ".fad" / "index.html"
        if path.is_file() and not path.is_symlink():
            webbrowser.open(path.resolve().as_uri())
        else:
            self.status.set("Indice non presente: completa almeno un download.")

    def reauthenticate(self):
        """Eseguito nel worker: nessun accesso ai widget."""
        from .env_config import read_credentials

        username, password = read_credentials(self.env_file)
        if username != self.login_username:
            password = None
        if not password:
            raise FadError("AUTH_REQUIRED", "Nuovo accesso manuale necessario; piano conservato.")
        try:
            return self.moodle.login(self.login_username, password)
        finally:
            password = None

    def open_catalog(self):
        workspace, account = Path(self.workspace.get()), self.account
        self.start(lambda: load_catalog(workspace, account), self.scanned)

    def read_report(self):
        from .storage import SafeRoot

        workspace = Path(self.workspace.get())

        def work():
            report = SafeRoot(workspace).json(".fad/report.json")
            if report is None:
                raise FadError("STATE", "Report locale non presente.")
            return report

        self.start(work, self.downloaded)

    def show_tasks(self, tasks, workspace):
        self.tasks, self.planned_workspace = tasks, workspace
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert(
            "end", "\n\n".join(f"{t.resource.name}\n  → {t.relative}" for t in tasks)
        )
        self.preview.configure(state="disabled")
        self.status.set(
            f"Anteprima recuperata: {len(tasks)} risorse. Controlla le destinazioni prima di scaricare."
        )

    def resume_plan(self):
        if not self.account:
            self.status.set("Accedi allo stesso account prima di recuperare il piano.")
            return
        workspace, account = Path(self.workspace.get()), self.account
        self.start(
            lambda: load_pending(workspace, account),
            lambda tasks: self.show_tasks(tasks, workspace),
        )

    def copy_conflicts(self):
        if not self.account:
            self.status.set("Accedi prima di scaricare copie alternative.")
            return
        from .services import alternate_tasks

        workspace, account = Path(self.workspace.get()), self.account
        self.start(
            lambda: alternate_tasks(workspace, account),
            lambda tasks: self.show_tasks(tasks, workspace),
        )

    def backup(self):
        workspace = Path(self.workspace.get())
        self.start(
            lambda: backup_state(workspace),
            lambda path: self.status.set("Backup dello stato creato: " + path),
        )

    def restore(self):
        workspace = Path(self.workspace.get())

        def finish(inventory):
            self.append("Temporanei rilevati: " + str(len(inventory["temporary_files"])))
            if not inventory["backups"]:
                self.status.set("Nessun backup disponibile.")
                return
            folder = simpledialog.askstring(
                "Ripristina stato",
                "Backup disponibili:\n" + "\n".join(inventory["backups"]),
                initialvalue=inventory["backups"][-1],
            )
            if folder and messagebox.askyesno(
                "Ripristina stato",
                "Ripristinare il backup? Lo stato attuale verrà conservato. I materiali non saranno modificati.",
            ):
                self.start(
                    lambda: restore_state(workspace, folder),
                    lambda _: self.status.set("Stato ripristinato. Riapri catalogo e report."),
                )

        self.start(lambda: recovery_inventory(workspace), finish)

    def edit_limits(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Limiti operativi")
        fields = {}
        for row, (key, value) in enumerate(asdict(self.limits).items()):
            ttk.Label(dialog, text=key).grid(row=row, column=0, padx=10, pady=4)
            fields[key] = tk.StringVar(value=str(value))
            ttk.Entry(dialog, textvariable=fields[key]).grid(row=row, column=1, padx=10)
        message = tk.StringVar(
            value="Dimensioni in byte; tempi in secondi. Salva impostazioni per conservarli."
        )
        ttk.Label(dialog, textvariable=message).grid(row=len(fields), columnspan=2, padx=10, pady=8)

        def apply():
            try:
                self.limits = Limits(**{key: int(var.get()) for key, var in fields.items()})
            except (ValueError, FadError):
                message.set("Valori non validi o oltre il massimo consentito.")
                return
            if self.client and hasattr(self.client, "limits"):
                self.client.limits = self.limits
            dialog.destroy()

        ttk.Button(dialog, text="Applica", command=apply).grid(
            row=len(fields) + 1, columnspan=2, pady=8
        )

    def cancel_work(self):
        event("gui.cancel_requested")
        self.cancel.set()

    def open_log(self):
        from . import observability

        if observability.log_path:
            webbrowser.open(observability.log_path.as_uri())
        else:
            self.status.set("Log su file disabilitati.")

    def db_login(self, register=False):
        username = simpledialog.askstring(
            "Registrazione DB" if register else "Accesso DB",
            "Nome utente DB (distinto dall'account FAD).\n"
            "3-40 lettere a-z, numeri o . _ -, senza spazi né accenti.\n"
            "Esempio: edoardo.querio",
            parent=self.window,
        )
        if not username:
            return
        password = simpledialog.askstring(
            "Utente DB", "Password utente DB (da 8 a 1024 caratteri):",
            show="*", parent=self.window,
        )
        if not password:
            return
        if register and password != simpledialog.askstring(
            "Utente DB", "Ripeti password:", show="*", parent=self.window
        ):
            self.status.set("Le password non coincidono.")
            return
        previous = self.db_session

        def work():
            if register:
                self.archive.register(username, password)
            session = self.archive.login(username, password)
            if previous:
                self.archive.logout(previous)
            return session

        def finish(session):
            self.close_db_views()
            self.db_session = session
            self.db_label.set("Utente DB: " + session.username)
            base = Path.home() / ("FAD-demo" if self.demo else "FAD")
            self.workspace.set(str(base / "utenti" / str(session.user_id)))
            self.catalog, self.mapping = Catalog(), {}
            self.populate()
            self.status.set("Utente DB connesso. Scansiona FAD o apri il tuo archivio.")

        self.start(work, finish)

    def db_logout(self):
        if not self.db_session:
            return
        session = self.db_session

        def finish(_):
            self.close_db_views()
            self.db_session = None
            self.db_label.set("Utente DB: nessuno")
            self.invalidate()
            self.status.set("Utente DB disconnesso. Il login FAD resta separato.")

        self.start(lambda: self.archive.logout(session), finish)

    def db_history(self):
        if not self.db_session:
            self.status.set("Accedi come utente DB.")
            return
        session = self.db_session

        def finish(rows):
            dialog = tk.Toplevel(self.window)
            self.db_dialogs.append(dialog)
            dialog.title("Archivio BLOB - " + session.username)
            dialog.geometry("1000x500")
            tree = ttk.Treeview(dialog, columns=("course", "status", "files"), show="tree headings")
            tree.heading("#0", text="Risorsa scaricata")
            for key, title in (("course", "Corso"), ("status", "Esito"), ("files", "File BLOB")):
                tree.heading(key, text=title)
            tree.pack(fill="both", expand=True)
            for row in rows:
                tree.insert(
                    "",
                    "end",
                    iid=str(row["id"]),
                    text=row["name"],
                    values=(row["course"], row["status"], row["file_count"]),
                )

            def restore():
                selected = tree.selection()
                if not selected:
                    return
                download_id = int(selected[0])

                def choose(files):
                    if not files:
                        self.status.set("Nessun BLOB per questa operazione.")
                        return
                    picker = tk.Toplevel(dialog)
                    self.db_dialogs.append(picker)
                    picker.title("File BLOB della risorsa")
                    picker.geometry("800x350")
                    items = ttk.Treeview(picker, columns=("bytes",), show="tree headings")
                    items.heading("#0", text="File principale e allegati")
                    items.heading("bytes", text="Byte")
                    items.pack(fill="both", expand=True)
                    for index, item in enumerate(files):
                        items.insert(
                            "",
                            "end",
                            iid=str(index),
                            text=item["relative_path"],
                            values=(item["size"],),
                        )

                    def save():
                        choice = items.selection()
                        if not choice:
                            return
                        item = files[int(choice[0])]
                        destination = filedialog.asksaveasfilename(
                            parent=picker,
                            title="Ripristina BLOB (scegliere un nuovo file)",
                            initialfile=Path(item["relative_path"]).name,
                        )
                        if destination:
                            self.start(
                                lambda: self.archive.restore(
                                    session, item["object_id"], Path(destination)
                                ),
                                lambda _: self.status.set("Oggetto ripristinato dal BLOB."),
                            )

                    ttk.Button(picker, text="Ripristina file selezionato", command=save).pack(
                        pady=6
                    )

                self.start(lambda: self.archive.files(session, download_id), choose)

            ttk.Button(dialog, text="File BLOB e ripristino", command=restore).pack(pady=8)
            ttk.Label(
                dialog, text="I file restano nel database anche se cancellati dal workspace."
            ).pack()

        self.start(lambda: self.archive.history(session), finish)

    def db_import(self):
        if not self.db_session:
            self.status.set("Accedi come utente DB prima di importare.")
            return
        session, workspace = self.db_session, Path(self.workspace.get())
        self.start(
            lambda: self.archive.import_workspace(session, workspace),
            lambda r: self.status.set(f"BLOB importati: {r['imported']}; problemi: {r['failed']}."),
        )

    def db_pdf(self):
        if not self.db_session:
            self.status.set("Accedi come utente DB per creare il tuo report.")
            return
        destination = filedialog.asksaveasfilename(
            title="Report personale download",
            defaultextension=".pdf",
            initialfile="report_download.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if destination:
            from .pdf_reports import export_user_report

            session = self.db_session
            self.start(
                lambda: export_user_report(self.archive, session, Path(destination)),
                lambda path: self.status.set("Report PDF salvato: " + str(path)),
            )

    def close_db_views(self):
        for dialog in self.db_dialogs:
            if dialog.winfo_exists():
                dialog.destroy()
        self.db_dialogs.clear()

    def close(self):
        if self.future and not messagebox.askyesno(
            "Operazione in corso", "Annullare e chiudere al termine della richiesta corrente?"
        ):
            return
        self.closing = True
        event("gui.close_requested")
        self.cancel.set()
        self.status.set("Chiusura in corso…")


def launch(demo=False, env_file=None, database=None):
    try:
        window = tk.Tk()
    except tk.TclError:
        print("Display grafico non disponibile. Usa --help per i comandi da terminale.")
        return 1
    try:
        App(window, demo, env_file, database)
    except FadError as exc:
        messagebox.showerror("Avvio non riuscito", str(exc))
        window.destroy()
        return 2
    except OSError:
        messagebox.showerror(
            "Avvio non riuscito",
            "Impossibile aprire il database: controllare percorso, permessi e spazio.",
        )
        window.destroy()
        return 2
    window.mainloop()
    return 0
