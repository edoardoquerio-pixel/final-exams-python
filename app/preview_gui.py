"""Cattura locale facoltativa della demo per la verifica visiva su Windows."""
import tkinter as tk
from pathlib import Path
from PIL import ImageGrab
from fad_downloader.gui import App

window = tk.Tk()
app = App(window, demo=True)
def capture():
    window.update_idletasks()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height())).save(Path(__file__).with_name("gui-preview.png"))
    app.pool.shutdown(wait=True)
    window.destroy()
window.after(1500, capture)
window.mainloop()
