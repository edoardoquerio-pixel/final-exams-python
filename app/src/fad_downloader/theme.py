"""Tema desktop condiviso, senza dipendenze grafiche esterne."""

from tkinter import font, ttk


COLORS = {
    "background": "#F1F5F9",
    "surface": "#FFFFFF",
    "text": "#172B4D",
    "muted": "#52647B",
    "border": "#D8E2ED",
    "accent": "#087F8C",
    "hover": "#066875",
    "selection": "#D9F1F1",
}


def apply_theme(window):
    """Clam permette colori coerenti anche su Windows e GNU/Linux."""
    c = COLORS
    available = set(font.families(window))
    family = next((f for f in ("Segoe UI", "Noto Sans", "DejaVu Sans") if f in available), "sans-serif")
    font.nametofont("TkDefaultFont").configure(family=family, size=10)
    font.nametofont("TkTextFont").configure(family=family, size=10)
    window.configure(background=c["background"])
    window.option_add("*Toplevel.background", c["background"])
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure(".", background=c["background"], foreground=c["text"], font=(family, 10))
    style.configure("TFrame", background=c["background"])
    style.configure("Card.TFrame", background=c["surface"])
    style.configure("TLabel", background=c["background"], foreground=c["text"])
    style.configure("Title.TLabel", font=(family, 25, "bold"))
    style.configure("Subtitle.TLabel", foreground=c["muted"], font=(family, 10))
    style.configure("Section.TLabel", font=(family, 14, "bold"))
    style.configure("Badge.TLabel", background=c["selection"], foreground=c["hover"], padding=(12, 6))
    style.configure("TButton", padding=(14, 9), background=c["surface"], bordercolor=c["border"],
                    lightcolor=c["surface"], darkcolor=c["surface"], borderwidth=1, focuscolor=c["accent"])
    style.map("TButton", background=[("active", "#E5EDF5"), ("disabled", "#EDF1F5")],
              foreground=[("disabled", "#8795A5")])
    style.configure("Primary.TButton", background=c["accent"], foreground="white",
                    bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
                    font=(family, 10, "bold"), padding=(24, 10))
    style.map("Primary.TButton", background=[("disabled", "#DCE5EB"), ("active", c["hover"])],
              foreground=[("disabled", "#8795A5"), ("!disabled", "white")])
    style.configure("TEntry", padding=8, fieldbackground=c["surface"], bordercolor=c["border"],
                    lightcolor=c["border"], darkcolor=c["border"])
    style.configure("TCombobox", padding=7, fieldbackground=c["surface"], bordercolor=c["border"])
    style.map("TCombobox", fieldbackground=[("readonly", c["surface"])])
    style.configure("TLabelframe", background=c["background"], borderwidth=0)
    style.configure("TLabelframe.Label", font=(family, 12, "bold"), background=c["background"])
    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"],
                    foreground=c["text"], rowheight=34, borderwidth=0)
    style.map("Treeview", background=[("selected", c["selection"])],
              foreground=[("selected", c["text"])])
    style.configure("Treeview.Heading", background="#E7EEF5", foreground=c["muted"],
                    font=(family, 10, "bold"), padding=(12, 12), relief="flat")
    style.configure("TNotebook", background=c["background"], borderwidth=0, tabmargins=(0, 8, 0, 0))
    style.configure("TNotebook.Tab", padding=(18, 10), background=c["background"], borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", c["surface"])],
              foreground=[("selected", c["accent"])])
    style.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor="#E0E8F0",
                    borderwidth=0, thickness=4)
    style.configure("Vertical.TScrollbar", background="#CBD6E2", troughcolor=c["surface"],
                    borderwidth=0, arrowsize=12)


def style_text(widget):
    c = COLORS
    widget.configure(background=c["surface"], foreground=c["text"],
                     insertbackground=c["accent"], selectbackground=c["selection"],
                     selectforeground=c["text"], relief="flat", borderwidth=0,
                     padx=18, pady=16, highlightthickness=0)
