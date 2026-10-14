"""Interfaccia italiana Tkinter. Tutte le operazioni lente passano dal worker."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from .credentials import CredentialStore
from .demo import DEMO_ACCOUNT, DemoHttp, catalog as demo_catalog
from .domain import Catalog, FadError, Naming
from .moodle import Moodle
from .network import HttpClient
from .services import Downloader, load_settings, plan, save_settings, verify


class App:
    def __init__(self, window, demo=False):
        self.window, self.demo = window, demo
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
        self.tasks = []
        self.plan_revision = 0
        self.last_failed = set()
        self.buttons = []
        window.title("FAD Downloader 0.0.1" + (" - Demo offline" if demo else ""))
        window.geometry("1120x780")
        window.minsize(820, 620)
        self.username, self.password = tk.StringVar(), tk.StringVar()
        self.remember = tk.BooleanVar()
        self.workspace = tk.StringVar(value=str(Path.home() / ("FAD-demo" if demo else "FAD")))
        self.search, self.type = tk.StringVar(), tk.StringVar(value="Tutti")
        self.course_template = tk.StringVar(value="{course_id}_{course_name}")
        self.section_template = tk.StringVar(value="{section_name}")
        self.materials, self.quizzes = tk.StringVar(value="Materiali"), tk.StringVar(value="Test")
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
        ttk.Checkbutton(login, text="Ricorda", variable=self.remember).pack(side="left")
        self.button(login, "Accedi", self.login)
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
            )
        ):
            ttk.Label(grid, text=label).grid(row=0, column=column, sticky="w")
            ttk.Entry(grid, textvariable=var).grid(row=1, column=column, sticky="ew", padx=3)
            grid.columnconfigure(column, weight=1)
        ttk.Label(
            paths,
            text="Segnaposto: {course_id}, {course_name}, {section_name}, {activity_id}. Seleziona un corso per associarlo a una cartella.",
        ).pack(anchor="w")
        actions = ttk.Frame(shell)
        actions.pack(fill="x")
        self.button(actions, "Scansiona FAD", self.scan)
        self.button(actions, "Seleziona tutto", self.select_all)
        self.button(actions, "Associa cartella", self.map_course)
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
        self.tree.column("type", width=130, stretch=False)
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
        ttk.Button(controls, text="Annulla", command=self.cancel.set).pack(side="left", padx=3)
        self.button(controls, "Verifica file", self.verify_files)
        self.button(controls, "Apri indice locale", self.open_index)
        self.progress = ttk.Progressbar(shell, mode="indeterminate")
        self.progress.pack(fill="x", pady=6)
        ttk.Label(shell, textvariable=self.status).pack(anchor="w")

    def naming(self):
        return Naming(
            self.course_template.get(),
            self.section_template.get(),
            self.materials.get(),
            self.quizzes.get(),
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
        self.future = self.pool.submit(function)
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
                self.status.set(str(exc))
                self.append(f"{exc.code}: {exc}")
            except Exception:
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
        username, password, remember = (
            self.username.get().strip(),
            self.password.get(),
            self.remember.get(),
        )
        if not username:
            self.status.set("Inserisci lo username.")
            return
        self.password.set("")
        self.invalidate()
        self.catalog = Catalog()
        self.populate()
        self.account = None

        def work():
            nonlocal password
            if self.client:
                self.client.close()
            if not password:
                password = CredentialStore().get(username)
            if not password:
                raise FadError("AUTH_REQUIRED", "Password richiesta.")
            self.client = HttpClient(self.cancel)
            self.moodle = Moodle(self.client)
            try:
                account = self.moodle.login(username, password)
                if remember:
                    try:
                        CredentialStore().save(username, password)
                    except FadError as exc:
                        self.emit(str(exc))
                return account
            finally:
                password = None

        self.start(work, self.logged_in)

    def logged_in(self, account):
        self.account, self.demo = account, False
        self.status.set("Accesso riuscito. Premi Scansiona FAD.")

    def logout(self):
        if self.client:
            self.client.close()
        self.account, self.moodle, self.client = None, None, None
        self.password.set("")
        self.catalog, self.mapping = Catalog(), {}
        self.populate()
        self.status.set("Sessione locale chiusa.")

    def forget(self):
        username = self.username.get().strip()
        if username:
            self.start(
                lambda: CredentialStore().delete(username),
                lambda _: self.status.set("Credenziale eliminata dal portachiavi."),
            )

    def scan(self):
        if not self.account:
            self.status.set("Accedi prima di scansionare.")
            return
        self.start(
            lambda: demo_catalog() if self.demo else self.moodle.scan(self.emit), self.scanned
        )

    def scanned(self, catalog):
        self.catalog = catalog
        self.populate()
        for warning in catalog.warnings:
            self.append(warning)
        self.status.set(
            f"{len(catalog.courses)} corsi, {len(catalog.resources)} risorse. Seleziona i contenuti e genera l'anteprima."
        )

    def populate(self):
        self.invalidate()
        self.tree.delete(*self.tree.get_children())
        self.nodes = {}
        search, mode = self.search.get().casefold(), self.type.get()
        for resource in self.catalog.resources:
            if (
                search
                and search not in (resource.name + resource.course + resource.section).casefold()
            ):
                continue
            if mode != "Tutti" and (resource.kind == "quiz_review") != (mode == "Test"):
                continue
            course_id = "course:" + str(resource.course_id)
            section_id = course_id + ":" + resource.section
            if not self.tree.exists(course_id):
                self.tree.insert("", "end", iid=course_id, text=resource.course, open=True)
            if not self.tree.exists(section_id):
                self.tree.insert(course_id, "end", iid=section_id, text=resource.section, open=True)
            self.tree.insert(
                section_id, "end", iid=resource.id, text=resource.name, values=(resource.kind,)
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
        self.start(
            lambda: save_settings(workspace, account, naming, mapping),
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
            lambda: Downloader(client, account).run(tasks, workspace, self.emit), self.downloaded
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

    def close(self):
        if self.future and not messagebox.askyesno(
            "Operazione in corso", "Annullare e chiudere al termine della richiesta corrente?"
        ):
            return
        self.closing = True
        self.cancel.set()
        self.status.set("Chiusura in corso…")


def launch(demo=False):
    try:
        window = tk.Tk()
    except tk.TclError:
        print("Display grafico non disponibile. Usa --help per i comandi da terminale.")
        return 1
    App(window, demo)
    window.mainloop()
    return 0
