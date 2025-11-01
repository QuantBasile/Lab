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
from ui.filters_panel import FiltersPanel
from ui.volume_sheet import VolumeSheet



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
        # Notebook with two tabs: Table and Volume
        self.nb = ttk.Notebook(self)
        self.nb.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Tab 1: Table
        tab_table = ttk.Frame(self.nb)
        self.table = TableFrame(tab_table)
        self.table.pack(fill="both", expand=True)
        self.nb.add(tab_table, text="Table")
        
        # Tab 2: Volume (Daily Σ TXN_AMT)
        tab_volume = ttk.Frame(self.nb)
        self.volume_sheet = VolumeSheet(tab_volume)
        self.volume_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_volume, text="Volume")

        # Estilos
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=22)
        
        # --- Panel de filtros dentro de un contenedor colapsable ---
        self.filters_wrap = ttk.Frame(self)           # contenedor que se puede ocultar
        self.filters_panel = FiltersPanel(self.filters_wrap)
        
        # barra superior de filtros: toggle
        toggle_row = ttk.Frame(self)
        toggle_row.pack(side="top", fill="x", padx=10, pady=(8, 0))
        self.btn_toggle_filters = ttk.Button(
            toggle_row, text="Ocultar filtros ▲", command=self._toggle_filters, state="disabled"
        )
        self.btn_toggle_filters.pack(side="left")
        
        # Botonera de filtros (aplicar / borrar)
        btnrow = ttk.Frame(self)
        btnrow.pack(side="top", fill="x", padx=10, pady=(6, 8))
        self.btn_apply = ttk.Button(btnrow, text="Aplicar filtros", command=self.on_apply_filters, state="disabled")
        self.btn_clear = ttk.Button(btnrow, text="Borrar filtros", command=self.on_clear_filters, state="disabled")
        self.btn_apply.pack(side="left")
        self.btn_clear.pack(side="left", padx=(8, 0))



        

    def on_generate(self):
        n_rows = int(self.rows_var.get())
        self.btn_generate.state(["disabled"])
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
    
        # Construir filtros dinámicamente según el DF recién generado
        self.filters_panel.build(df)
    
        # Mostrar el contenedor de filtros (pestaña visible y botón habilitado)
        self._show_filters()
        self.btn_apply.state(["!disabled"])
        self.btn_clear.state(["!disabled"]) 
    
        # Refrescar tabla con el dataframe (filtrado = original al inicio)
        self._refresh_views()


        
    def on_apply_filters(self):
        try:
            spec = self.filters_panel.get_filters()
            self.service.apply_filters(spec)
        except Exception:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", "Falló la aplicación de filtros.")
            return
        self._refresh_views()
    
    def on_clear_filters(self):
        self.filters_panel.reset()
        self.service.clear_filters()
        self._refresh_views()

    
    def _refresh_views(self):
        df_view = self.service.dataframe_filtered.head(self.MAX_DISPLAY).copy()
        self.table.show_dataframe(df_view)
    
        # Full filtered DF for plotting (no head limit)
        df_full = self.service.dataframe_filtered
        self.volume_sheet.update_plot(df_full)

        
    def _show_filters(self):
        # mostrar contenedor y panel si no está visible
        if not self.filters_wrap.winfo_manager():
            self.filters_wrap.pack(side="top", fill="x", padx=10, pady=(0, 8))
            self.filters_panel.pack(side="top", fill="x")
            self.btn_toggle_filters.configure(text="Ocultar filtros ▲")
        self.btn_toggle_filters.state(["!disabled"])
    
    def _hide_filters(self):
        if self.filters_wrap.winfo_manager():
            self.filters_wrap.pack_forget()
            self.btn_toggle_filters.configure(text="Mostrar filtros ▼")
    
    def _toggle_filters(self):
        if self.filters_wrap.winfo_manager():
            self._hide_filters()
        else:
            self._show_filters()



