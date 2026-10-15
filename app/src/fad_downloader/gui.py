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
from .services import Downloader, load_settings, plan, save_settings, verify


class App:
    def __init__(self, window, demo=False, env_file=None):
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
        self.buttons = []
        window.title("FAD Downloader 0.1.0" + (" - Demo offline" if demo else ""))
        window.geometry("1220x860")
        window.minsize(1050, 740)
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
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side="left", padx=3, pady=3)
        self.buttons.append(button)
        return button

    def build(self):
        shell = ttk.Frame(self.window, padding=12)
        shell.pack(fill="both", expand=True)
        login = ttk.LabelFrame(shell, text="1. Accesso", padding=7)
        login.pack(fill="x")
        ttk.Label(login, text="Username").pack(side="left")
        ttk.Entry(login, textvariable=self.username, width=20).pack(side="left", padx=5)
        ttk.Label(login, text="Password").pack(side="left")
        ttk.Entry(login, textvariable=self.password, show="•", width=20).pack(side="left", padx=5)
        ttk.Label(login, text="Salvataggio automatico in .env").pack(side="left", padx=5)
        self.button(login, "Accedi", self.login)
        self.button(login, "Carica .env", self.reload_credentials)
        self.button(login, "Esci account", self.logout)
        self.button(login, "Dimentica password", self.forget)
        paths = ttk.LabelFrame(shell, text="2. Cartelle e nomenclatura", padding=7)
        paths.pack(fill="x", pady=8)
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
            "#0", text="Seleziona corsi, sezioni o attività (Ctrl/Shift per selezione multipla)"
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
        notebook.add(self.log, text="Messaggi e report")
        controls = ttk.Frame(shell)
        controls.pack(fill="x")
        self.button(controls, "Anteprima", self.preview_plan)
        self.button(controls, "Scarica piano", self.download)
        self.button(controls, "Ritenta falliti", self.retry)
        ttk.Button(controls, text="Annulla", command=self.cancel_work).pack(side="left", padx=3)
        self.button(controls, "Verifica file", self.verify_files)
        self.button(controls, "Apri indice locale", self.open_index)
        local = ttk.Frame(shell)
        local.pack(fill="x")
        self.button(local, "Apri catalogo offline", self.open_catalog)
        self.button(local, "Leggi report", self.read_report)
        self.button(local, "Recupera piano", self.resume_plan)
        self.button(local, "Copia conflitti", self.copy_conflicts)
        self.button(local, "Backup stato", self.backup)
        self.button(local, "Ripristina backup", self.restore)
        self.button(local, "Apri log", self.open_log)
        self.progress = ttk.Progressbar(shell, mode="indeterminate")
        self.progress.pack(fill="x", pady=6)
        ttk.Label(shell, textvariable=self.status).pack(anchor="w")

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
            self.pool.shutdown(wait=False)
            self.window.destroy()
            return
        self.window.after(100, self.poll)

    def login(self):
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
            catalog = demo_catalog() if self.demo else self.moodle.scan(self.emit)
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
        if not self.account or not self.client:
            self.status.set(
                "Accedi prima di scaricare; il catalogo offline è consultabile senza login."
            )
            return
        if not self.tasks:
            self.status.set("Genera prima l'anteprima aggiornata.")
            return
        tasks, client, account, workspace = (
            list(self.tasks),
            self.client,
            self.account,
            self.planned_workspace,
        )
        self.start(
            lambda: Downloader(client, account, None if self.demo else self.reauthenticate).run(
                tasks, workspace, self.emit
            ),
            self.downloaded,
        )

    def downloaded(self, report):
        self.last_failed = {
            r["resource_id"]
            for r in report["results"]
            if r["status"] in {"fallito", "annullato", "conflitto"}
        }
        for result in report["results"]:
            self.append(f"{result['status']}: {result['name']} {result['message']}")
        self.status.set(" | ".join(f"{k}: {v}" for k, v in report["counts"].items()))

    def retry(self):
        nodes = [key for key in self.last_failed if self.tree.exists(key)]
        self.tree.selection_set(nodes)
        self.preview_plan()

    def verify_files(self):
        workspace = Path(self.workspace.get())

        def finish(result):
            self.status.set(
                f"Verificati {result['checked']} file; problemi: {len(result['issues'])}."
            )
            for issue in result["issues"]:
                self.append(issue)

        self.start(lambda: verify(workspace), finish)

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

    def close(self):
        if self.future and not messagebox.askyesno(
            "Operazione in corso", "Annullare e chiudere al termine della richiesta corrente?"
        ):
            return
        self.closing = True
        event("gui.close_requested")
        self.cancel.set()
        self.status.set("Chiusura in corso…")


def launch(demo=False, env_file=None):
    try:
        window = tk.Tk()
    except tk.TclError:
        print("Display grafico non disponibile. Usa --help per i comandi da terminale.")
        return 1
    App(window, demo, env_file)
    window.mainloop()
    return 0
