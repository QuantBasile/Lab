#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:04:39 2025

@author: fran
"""

import tkinter as tk
from tkinter import ttk
from ui.main_window import MainWindow
from utils.logging_config import configure_logging







def run():
    configure_logging()
    root = tk.Tk()
    root.title("Laboratorio Marktanteil – v0.1 (Tkinter)")
    root.geometry("1200x700")
    
    
    # --- ESTILO GLOBAL TIPO Paarchen (Treeview pro) ---
    PALETTE = {
        "bg":"#f5f7fb","panel":"#ffffff","panel2":"#f0f3f9",
        "heading_bg":"#111827","heading_fg":"#ffffff",
        "row_even":"#fbfdff","row_odd":"#f2f6fb","hl":"#fff3c4",
    }
    try:
        root.configure(bg=PALETTE["bg"])
    except Exception:
        pass
    
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    
    # Fuentes “tipo Segoe” si están disponibles; si no, caerá en TkDefaultFont sin romper
    default_font = ("Segoe UI", 11)
    header_font  = ("Segoe UI Semibold", 11)
    
    style.configure(
        "Treeview",
        background=PALETTE["panel"],
        foreground="#111111",
        rowheight=28,
        fieldbackground=PALETTE["panel"],
        font=default_font,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=PALETTE["heading_bg"],
        foreground=PALETTE["heading_fg"],
        font=header_font,
        relief="flat",
        padding=(8, 6),
    )
    style.map(
        "Treeview",
        background=[("selected", "#cfe8ff")],
        foreground=[("selected", "#111111")],
    )
    
    
    app = MainWindow(master=root)
    app.pack(fill="both", expand=True)
    
    
    root.mainloop()