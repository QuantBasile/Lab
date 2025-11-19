#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tkinter bootstrap and global styling for the Marktanteil Laboratory app.
"""

import tkinter as tk
from tkinter import ttk

from ui.main_window import MainWindow


# Global palette for the application
PAL = {
    "page": "#ffffff",
    "topbar": "#1e40af",
    "topbar_fg": "#ffffff",
    "panel": "#ffffff",
    "sidebar": "#e6f0ff",
    "actions": "#eef4ff",
    "primary": "#2563eb",
    "primary_fg": "#ffffff",
    "primary_active": "#1d4ed8",
    "tab_bg": "#e6f0ff",
    "tab_sel_bg": "#2563eb",
    "tab_sel_fg": "#ffffff",
    "tab_fg": "#0b0b0b",
}


def _configure_styles(root: tk.Tk) -> None:
    """Configure ttk styles used across the UI."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        # fall back silently to default theme
        pass

    # Topbar
    style.configure(
        "Topbar.TFrame",
        background=PAL["topbar"],
    )
    style.configure(
        "Topbar.TLabel",
        background=PAL["topbar"],
        foreground=PAL["topbar_fg"],
        font=("Segoe UI Semibold", 12),
    )

    # Sidebar
    style.configure("Sidebar.TFrame", background=PAL["sidebar"])
    style.configure(
        "SidebarHeader.TLabel",
        background=PAL["sidebar"],
        foreground="#0b0b0b",
        font=("Segoe UI Semibold", 10),
    )
    style.configure("Nav.TButton", padding=(10, 8), anchor="w")
    style.map("Nav.TButton", background=[("active", "#d9e8ff")])

    # Actions bar
    style.configure("Actions.TFrame", background=PAL["actions"])

    # Cards / notebook
    style.configure("Card.TFrame", background=PAL["panel"])
    style.configure(
        "CardInner.TFrame",
        background=PAL["panel"],
        padding=(12, 10),
    )

    # --- Custom notebook (tabs) ---
    style.configure("CustomNotebook", background=PAL["panel"], borderwidth=0)
    style.layout("CustomNotebook", style.layout("TNotebook"))
    style.layout("CustomNotebook.Tab", style.layout("TNotebook.Tab"))

    style.configure(
        "CustomNotebook",
        background=PAL["panel"],
        borderwidth=0,
    )
    style.configure(
        "CustomNotebook.Tab",
        padding=(20, 10),
        borderwidth=0,
        font=("Segoe UI Semibold", 10),
        background=PAL["tab_bg"],
        foreground=PAL["tab_fg"],
    )
    style.map(
        "CustomNotebook.Tab",
        background=[("selected", PAL["tab_sel_bg"])],
        foreground=[("selected", PAL["tab_sel_fg"])],
    )

    # Buttons ttk
    style.configure(
        "Primary.TButton",
        background=PAL["primary"],
        foreground=PAL["primary_fg"],
        padding=(12, 6),
    )
    style.map(
        "Primary.TButton",
        background=[("active", PAL["primary_active"])],
    )
    style.configure("Secondary.TButton", padding=(10, 5))


def run() -> None:
    """Initialize and run the main Tkinter event loop."""
    root = tk.Tk()
    root.title("Laboratorio Marktanteil – v0.1 (Tkinter)")
    root.geometry("1200x700")
    root.configure(bg=PAL["page"])

    _configure_styles(root)

    app = MainWindow(master=root)
    app.pack(fill="both", expand=True)

    root.mainloop()
