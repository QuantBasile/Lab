#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:05:42 2025

@author: fran
"""
import tkinter as tk
from tkinter import ttk


class TableFrame(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self._tree = None
        self._columns = []
        self._build()
        
    
    def _build(self):
        self._tree = ttk.Treeview(self, show="headings")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscroll=vsb.set, xscroll=hsb.set)
    
    
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    
    
    def _setup_columns(self, columns):
        self._columns = list(columns)
        self._tree.configure(columns=self._columns)
        for col in self._columns:
            self._tree.heading(col, text=col, command=lambda c=col: self._sort_by(c, False))
            self._tree.column(col, width=120, anchor="w")
    
    
    def show_dataframe(self, df):
        # limpiar
        for c in self._tree.get_children():
            self._tree.delete(c)
        if not list(df.columns):
            return
        self._setup_columns(df.columns)
        # insertar
        rows = df.itertuples(index=False, name=None)
        for row in rows:
            values = [self._format(v) for v in row]
            self._tree.insert("", "end", values=values)
    
    
    def _format(self, v):
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)
    
    
    def _sort_by(self, col, descending):
    # ordenar visualmente las filas actuales
        data = [(self._tree.set(k, col), k) for k in self._tree.get_children("")]
        try:
            data.sort(key=lambda t: float(t[0]), reverse=descending)
        except ValueError:
            data.sort(key=lambda t: t[0], reverse=descending)
        for index, (val, k) in enumerate(data):
            self._tree.move(k, "", index)
        # alternar
        self._tree.heading(col, command=lambda: self._sort_by(col, not descending))