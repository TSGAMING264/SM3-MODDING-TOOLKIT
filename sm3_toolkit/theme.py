from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#171717",
    "panel": "#202020",
    "panel2": "#252526",
    "field": "#2B2B2B",
    "fg": "#F2F2F2",
    "muted": "#BDBDBD",
    "soft": "#8E8E8E",
    "accent": "#3B4048",
    "accent_hover": "#464B54",
    "accent_pressed": "#2B3037",
    "brand": "#DCE6F2",
    "byline": "#C7CCD6",
    "select": "#3F424A",
    "button": "#30343B",
    "button_hover": "#3A3D45",
    "button_pressed": "#23262C",
    "bad": "#FF9A9A",
}


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Root.TFrame", background=COLORS["bg"])
    style.configure("Body.TFrame", background=COLORS["bg"])
    style.configure("Header.TFrame", background="#101318")
    style.configure("Card.TFrame", background=COLORS["panel"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("Byline.TLabel", background=COLORS["bg"], foreground=COLORS["byline"], font=("Segoe UI", 10, "bold"))
    style.configure("CardLabel.TLabel", background=COLORS["panel"], foreground=COLORS["fg"])
    style.configure("HeaderTitle.TLabel", background="#101318", foreground=COLORS["brand"], font=("Segoe UI", 22, "bold"))
    style.configure("HeaderMeta.TLabel", background="#101318", foreground=COLORS["muted"], font=("Segoe UI", 10))
    style.configure("SectionTitle.TLabel", background=COLORS["bg"], foreground=COLORS["fg"], font=("Segoe UI", 14, "bold"))
    style.configure("Status.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
    style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["fg"], insertcolor=COLORS["fg"], bordercolor="#4B5563")
    style.map("TEntry",
        fieldbackground=[("disabled", COLORS["field"]), ("readonly", COLORS["field"]), ("focus", COLORS["field"])],
        foreground=[("disabled", COLORS["muted"]), ("readonly", COLORS["fg"]), ("focus", COLORS["fg"])],
    )
    style.configure("TCombobox",
        fieldbackground=COLORS["field"],
        background=COLORS["field"],
        foreground=COLORS["fg"],
        selectbackground=COLORS["field"],
        selectforeground=COLORS["fg"],
        insertcolor=COLORS["fg"],
        arrowcolor=COLORS["fg"],
        bordercolor="#4B5563",
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", COLORS["field"]), ("disabled", COLORS["field"]), ("focus", COLORS["field"])],
        background=[("readonly", COLORS["field"]), ("disabled", COLORS["field"]), ("active", COLORS["panel2"])],
        foreground=[("readonly", COLORS["fg"]), ("disabled", COLORS["muted"]), ("focus", COLORS["fg"])],
        selectbackground=[("readonly", COLORS["field"]), ("focus", COLORS["field"])],
        selectforeground=[("readonly", COLORS["fg"]), ("focus", COLORS["fg"])],
    )
    try:
        root.option_add("*TCombobox*Listbox.background", COLORS["field"])
        root.option_add("*TCombobox*Listbox.foreground", COLORS["fg"])
        root.option_add("*TCombobox*Listbox.selectBackground", COLORS["select"])
        root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        root.option_add("*Entry.background", COLORS["field"])
        root.option_add("*Entry.foreground", COLORS["fg"])
        root.option_add("*Entry.insertBackground", COLORS["fg"])
    except Exception:
        pass
    style.configure("TCheckbutton", background=COLORS["bg"], foreground=COLORS["fg"])
    style.configure("TButton", background=COLORS["button"], foreground=COLORS["fg"], padding=(10, 6), bordercolor="#555555")
    style.map("TButton", background=[("pressed", COLORS["button_pressed"]), ("active", COLORS["button_hover"])])
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="#FFFFFF", padding=(12, 6), font=("Segoe UI", 9, "bold"))
    style.map("Accent.TButton", background=[("pressed", COLORS["accent_pressed"]), ("active", COLORS["accent_hover"])])
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=COLORS["panel"], foreground=COLORS["muted"], padding=(11, 7))
    style.map("TNotebook.Tab", background=[("selected", COLORS["panel2"]), ("active", COLORS["button"])], foreground=[("selected", COLORS["fg"]), ("active", COLORS["fg"])])
    style.configure("Treeview", background=COLORS["field"], fieldbackground=COLORS["field"], foreground=COLORS["fg"])
    style.configure("Treeview.Heading", background=COLORS["panel"], foreground=COLORS["fg"])
    style.map("Treeview", background=[("selected", COLORS["select"])], foreground=[("selected", "#FFFFFF")])
    return style

