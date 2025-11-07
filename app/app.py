#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:04:39 2025

@author: fran
"""

import tkinter as tk
from tkinter import ttk
from ui.main_window import MainWindow



def run():
    root = tk.Tk()
    root.title("Laboratorio Marktanteil – v0.1 (Tkinter)")
    root.geometry("1200x700")
    
    PAL = {
        "page": "#ffffff",
        "topbar": "#1e40af",  "topbar_fg": "#ffffff",
        "panel": "#ffffff",
        "sidebar": "#e6f0ff",
        "actions": "#eef4ff",
        "primary": "#2563eb", "primary_fg": "#ffffff",
        "primary_active": "#1d4ed8",
        "tab_bg": "#e6f0ff", "tab_sel_bg": "#2563eb",
        "tab_sel_fg": "#ffffff", "tab_fg": "#0b0b0b",
    }
    
    root.configure(bg=PAL["page"])
    style = ttk.Style(root)
    try: style.theme_use("clam")
    except: pass
    
    # Topbar
    style.configure("Topbar.TFrame", background=PAL["topbar"])
    style.configure("Topbar.TLabel", background=PAL["topbar"], foreground=PAL["topbar_fg"],
                    font=("Segoe UI Semibold", 12))
    
    # Sidebar
    style.configure("Sidebar.TFrame", background=PAL["sidebar"])
    style.configure("SidebarHeader.TLabel", background=PAL["sidebar"], foreground="#0b0b0b",
                    font=("Segoe UI Semibold", 10))
    style.configure("Nav.TButton", padding=(10, 8), anchor="w")
    style.map("Nav.TButton", background=[("active", "#d9e8ff")])
    
    # Actions bar
    style.configure("Actions.TFrame", background=PAL["actions"])
    
    # Cards / notebook
    style.configure("Card.TFrame", background=PAL["panel"])
    style.configure("CardInner.TFrame", background=PAL["panel"], padding=(12, 10))
    
    # --- Tabs con estilo (Notebook) ---
    style.configure("CustomNotebook", background=PAL["panel"], borderwidth=0)
    # ==== Estilo custom para Notebook (tabs) ====
    # 1) Registrar el layout base para que exista "CustomNotebook"
    style.layout("CustomNotebook", style.layout("TNotebook"))
    # 2) Registrar el layout de las pestañas
    style.layout("CustomNotebook.Tab", style.layout("TNotebook.Tab"))
    
    # 3) Configurar el propio Notebook
    style.configure("CustomNotebook", background=PAL["panel"], borderwidth=0)
    
    # 4) Estilo de pestañas tipo "chips"
    style.configure(
        "CustomNotebook.Tab",
        padding=(20, 10),
        borderwidth=0,
        font=("Segoe UI Semibold", 10),
        background="#e6f0ff",   # inactiva
        foreground="#0b0b0b",
    )
    style.map(
        "CustomNotebook.Tab",
        background=[("selected", "#2563eb")],  # activa
        foreground=[("selected", "#ffffff")],
    )


    
    # Botones ttk (por si los usas en otras partes)
    style.configure("Primary.TButton", background=PAL["primary"], foreground=PAL["primary_fg"], padding=(12, 6))
    style.map("Primary.TButton", background=[("active", PAL["primary_active"])])
    style.configure("Secondary.TButton", padding=(10, 5))




    
    
    app = MainWindow(master=root)
    app.pack(fill="both", expand=True)
    
    
    root.mainloop()