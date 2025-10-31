#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:05:23 2025

@author: fran
"""

import tkinter as tk
from tkinter import ttk, messagebox
from services.data_service import DataService
from ui.table_widget import TableFrame
import traceback




class MainWindow(tk.Frame):
    MAX_DISPLAY = 1000
    
    
    def __init__(self, master=None):
        super().__init__(master)
        self.service = DataService()
        self._build_ui()
    
    
    def _build_ui(self):
        # Controles superiores
        controls = ttk.Frame(self)
        controls.pack(side="top", fill="x", padx=10, pady=8)
        
        
        ttk.Label(controls, text="Filas a generar:").pack(side="left")
        
        
        self.rows_var = tk.IntVar(value=1_000_000)
        self.rows_spin = ttk.Spinbox(controls, from_=1000, to=5_000_000, increment=50_000,
        textvariable=self.rows_var, width=12)
        self.rows_spin.pack(side="left", padx=(6, 12))
        
        
        self.btn_generate = ttk.Button(controls, text="Generar datos fake (3 meses)", command=self.on_generate)
        self.btn_generate.pack(side="left")
        
        
        # Tabla
        self.table = TableFrame(self)
        self.table.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        
        # Estilos
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=22)
    
    
    def on_generate(self):
        n_rows = int(self.rows_var.get())
        self.btn_generate.state(["disabled"]) # evitar clicks múltiples
        self.update_idletasks()
        try:
            df = self.service.generate_fake_transactions(n_rows=n_rows)
        except Exception:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", "No se pudieron generar los datos. Revisa logs.")
            return
        finally:
            self.btn_generate.state(["!disabled"])
        
        
        df_view = df.head(self.MAX_DISPLAY).copy()
        self.table.show_dataframe(df_view)